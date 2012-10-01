#!/usr/bin/env python

import argparse
import errno
import grp
import json
import logging
import numbers
import os
import pwd
import shutil
import stat

from StringIO import StringIO
from sys import argv, exit
from time import time

from fuse import FUSE, FuseOSError, ENOENT, EACCES, EINVAL, Operations, LoggingMixIn, fuse_get_context

class JsonFS(LoggingMixIn, Operations):
    '''
    A JSON filesystem.
    '''

    ATTRS = ('st_uid', 'st_gid', 'st_mode', 'st_atime', 'st_mtime', 'st_size')
    STATV = ('f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag', 'f_frsize', 'f_namemax')

    def __init__(self, path, mountpoint='.', args={}):
        self.log.setLevel(args.log)
        self.log.debug("path: %s mountpoint: %s args: %s", path, mountpoint, repr(args))

        self.path = os.path.abspath(path)
        self.mountpoint = os.path.abspath(mountpoint)
        self.args = args
        self.fd = 0

        self.log.debug("SELF: path: %s mountpoint: %s args: %s", self.path, self.mountpoint, repr(self.args))

        with open(path) as f:
            self.document = json.load(f)

    def _s2p(self, string):
        """
        Convert a string path into a list of path parts.
        """
        plist = []

        (fore, aft) = os.path.split(string)
        while len(aft) != 0:
            plist.insert(0, aft)
            (fore, aft) = os.path.split(fore)

        return plist

    def _p2d(self, path):
        """
        Convert a string path into a tuple containing the parent object, key,
        and document.
        """
        self.log.debug("Path: %s (%s)" % (path, type(path)))

        try:
            parent = None
            key = None
            doc = self.document
            for part in self._s2p(path):
                if isinstance(doc, list):
                    part = int(part)
                parent = doc
                key = part
                doc = doc[part]
        except KeyError:
            raise FuseOSError(ENOENT)
        except IndexError:
            raise FuseOSError(ENOENT)

        return (parent, key, doc)

    def _attrs(self, path):
        doc = self._p2d(path)[2]
        attrs = {}

        if isinstance(doc, basestring):
            attrs['user.json.type'] = 'string'
        elif isinstance(doc, bool):
            attrs['user.json.type'] = 'boolean'
        elif isinstance(doc, numbers.Number):
            attrs['user.json.type'] = 'number'

            if isinstance(doc, numbers.Integral):
                attrs['user.json.number.type'] = 'integral'
            elif isinstance(doc, numbers.Real):
                attrs['user.json.number.type'] = 'real'
        elif isinstance(doc, dict):
            attrs['user.json.type'] = 'object'
        elif isinstance(doc, list):
            attrs['user.json.type'] = 'array'
        elif isinstance(doc, type(None)):
            attrs['user.json.type'] = 'null'
        else:
            attrs['user.json.type'] = 'invalid'

        return attrs

    def access(self, path, mode):
        # Inherit access from document.
        if not os.access(self.path, mode):
            raise FuseOSError(EACCES)

    chmod = None
#    def chmod(self, path, mode):
#        _path = path[1:]
#        apath = os.path.join(self.tmp, _path)
#        status = os.chmod(apath, mode)
#
#        self.__save_attributes(path, "hgfs[chmod]: %s %o" % (_path, mode))
#
#        return status

    chown = None
#    def chown(self, path, uid, gid):
#        _path = path[1:]
#        apath = os.path.join(self.tmp, _path)
#        status = os.chown(apath, uid, gid)
#
#        self.__save_attributes(path, "hgfs[chown]: %s %d %d" % (_path, uid, gid))
#
#        return status

    def create(self, path, mode, fi=None):
        ppath = '/'
        parts = self._s2p(path)

        if len(parts) > 1:
            ppath = os.path.join(*parts[:-1])

        (parent, key, doc) = self._p2d(ppath)
        if isinstance(doc, list):
            index = int(parts[-1])
            if index < 0:
                raise FuseOSError(EINVAL)
            doc.extend([u''] * ((index + 1) - len(doc)))
            doc[index] = u''
            self.log.debug("Doc: " + repr(doc))
        else:
            doc[parts[-1]] = u''

        self.fd += 1

        return self.fd

    def destroy(self, path):
        with open(self.path, 'w') as f:
            json.dump(self.document, f, indent=2, sort_keys=True)

    def flush(self, path, fh):
        pass

    def fsync(self, path, datasync, fh):
        with open(self.path, 'w') as f:
            json.dump(self.document, f, indent=2, sort_keys=True)

    def fsyncdir(self, path, datasync, fh):
        with open(self.path, 'w') as f:
            json.dump(self.document, f, indent=2, sort_keys=True)

    def getattr(self, path, fh=None):
        doc = self._p2d(path)[2]

        # Inherit from document.
        st = os.lstat(self.path)
        self.log.debug("Stat: " + str(st))

        std = dict((key, getattr(st, key)) for key in self.ATTRS)

        # Convert type to directory.
        if isinstance(doc, (dict, list)):
            new_mode = std['st_mode']
            new_mode ^= stat.S_IFREG
            new_mode |= stat.S_IFDIR

            std['st_mode'] = new_mode

        # Update the number of links.
        if isinstance(doc, dict):
            std['st_nlink'] = 2 + len(doc.keys())
        elif isinstance(doc, list):
            std['st_nlink'] = 2 + len(doc)
        else:
            std['st_nlink'] = 1

        # Update the size.
        if isinstance(doc, (dict, list)):
            std['st_size'] = 0
        elif isinstance(doc, basestring):
            std['st_size'] = len(doc)
        else:
            std['st_size'] = len(json.dumps(doc, indent=2, sort_keys=True))

        return std

    def getxattr(self, path, name, position=0):
        try:
            value = self._attrs(path)[name]
        except:
            raise FuseOSError(EINVAL)

        return value

    init = None
#    def init(self, path):
#        pass

    link = None
#    def link(self, target, source):
#        pass

    def listxattr(self, path):
        return self._attrs(path).keys()

    def mkdir(self, path, mode):
        ppath = '/'
        parts = self._s2p(path)

        if len(parts) > 1:
            ppath = os.path.join(*parts[:-1])

        (parent, key, doc) = self._p2d(ppath)
        if isinstance(doc, list):
            index = int(parts[-1])
            if index < 0:
                raise FuseOSError(EINVAL)
            doc.extend([dict()] * ((index + 1) - len(doc)))
            doc[index] = dict()
            self.log.debug("Doc: " + repr(doc))
        else:
            doc[parts[-1]] = dict()

        return 0

    mknod = None

    def open(self, path, flags):
        doc = self._p2d(path)[2]

        self.fd += 1

        return self.fd

    opendir = None

    def read(self, path, size, offset, fh):
        doc = self._p2d(path)[2]

        if isinstance(doc, basestring):
            unidata = doc.encode('latin1')
            return unidata[offset:offset + size]
        else:
            return json.dumps(doc, indent=2, sort_keys=True)[offset:offset + size]

    def readdir(self, path, fh):
        doc = self._p2d(path)[2]

        if isinstance(doc, dict):
            return ['.', '..'] + doc.keys()
        elif isinstance(doc, list):
            return ['.', '..'] + map(repr, range(len(doc)))

#    readlink = None
#    def readlink(self, path):
#        if self.args.clone: dispatch(request(['--cwd', self.tmp, 'pull', '-u']))
#
#        apath = os.path.join(self.tmp, path[1:])
#        return os.readlink(apath)

#    release = None
#    def release(self, path, fh):
#        return os.close(fh)

#    releasedir = None
#    def releasedir(self, path, fh):
#        return os.close(fh)

    removexattr = None
#    def removexattr(self, path, name):
#        pass

    def rename(self, old, new):
        ppath = '/'
        parts = self._s2p(new)

        if len(parts) > 1:
            ppath = os.path.join(*parts[:-1])

        (parent, key, doc) = self._p2d(ppath)

        (o_parent, o_key, o_doc) = self._p2d(old)
        doc[parts[-1]] = o_doc
        del o_parent[o_key]

    def rmdir(self, path):
        (parent, key, doc) = self._p2d(path)
        del parent[key]

        return 0

    def setxattr(self, path, name, value, options, position=0):
        (parent, key, doc) = self._p2d(path)
        attrs = self._attrs(path)

        if name == 'user.json.type':
            if isinstance(doc, basestring):
                if value == 'string':
                    pass
                elif value == 'number':
                    new_doc = json.loads(doc)
                    if not isinstance(new_doc, numbers.Number):
                        raise FuseOSError(EINVAL)
                    parent[key] = new_doc
                elif value == 'object':
                    new_doc = json.loads(doc)
                    if not isinstance(new_doc, dict):
                        raise FuseOSError(EINVAL)
                    parent[key] = new_doc
                elif value == 'array':
                    new_doc = json.loads(doc)
                    if not isinstance(new_doc, list):
                        raise FuseOSError(EINVAL)
                    parent[key] = new_doc
                elif value == 'boolean':
                    new_doc = json.loads(doc)
                    if not isinstance(new_doc, bool):
                        raise FuseOSError(EINVAL)
                    parent[key] = new_doc
                elif value == 'null':
                    new_doc = json.loads(doc)
                    if not isinstance(new_doc, type(None)):
                        raise FuseOSError(EINVAL)
                    parent[key] = new_doc
                else:
                    raise FuseOSError(EINVAL)
            elif isinstance(doc, bool):
                if value == 'string':
                    parent[key] = json.dumps(doc, indent=2, sort_keys=True)
                elif value == 'number':
                    parent[key] = int(doc)
                elif value == 'boolean':
                    pass
                else:
                    raise FuseOSError(EINVAL)
            elif isinstance(doc, numbers.Number):
                if value == 'string':
                    parent[key] = json.dumps(doc, indent=2, sort_keys=True)
                elif value == 'number':
                    pass
                elif value == 'boolean':
                    parent[key] = bool(doc)
                else:
                    raise FuseOSError(EINVAL)
            elif isinstance(doc, dict):
                if value == 'string':
                    parent[key] = json.dumps(doc, indent=2, sort_keys=True)
                elif value == 'object':
                    pass
                elif value == 'array':
                    # Possible... but alot of work.
                    raise FuseOSError(EINVAL)
                else:
                    raise FuseOSError(EINVAL)
            elif isinstance(doc, list):
                if value == 'string':
                    parent[key] = json.dumps(doc, indent=2, sort_keys=True)
                elif value == 'object':
                    # Possible... but alot of work.
                    raise FuseOSError(EINVAL)
                elif value == 'array':
                    pass
                else:
                    raise FuseOSError(EINVAL)
            elif isinstance(doc, type(None)):
                if value == 'string':
                    parent[key] = json.dumps(doc, indent=2, sort_keys=True)
                elif value == 'null':
                    pass
                else:
                    raise FuseOSError(EINVAL)
            else:
                raise FuseOSError(EINVAL)
        elif name == 'user.json.number.type':
            if not isinstance(doc, numbers.Number):
                raise FuseOSError(EINVAL)

            if value == 'integral':
                parent[key] = int(doc)
            elif value == 'real':
                parent[key] = float(doc)
            else:
                raise FuseOSError(EINVAL)

    def statfs(self, path):
        stv = os.statvfs(self.path)
        return dict((key, getattr(stv, key)) for key in self.STATV)

    symlink = None
#    def symlink(self, target, source):
#        _source = source[1:]
#        _target = target[1:]
#
#        asource = os.path.join(self.tmp, _source)
#        atarget = os.path.join(self.tmp, _target)
#
#        status = os.symlink(source, atarget)
#
#        uid, gid, pid = fuse_get_context()
#        username = pwd.getpwuid(uid)[0]
#
#        dispatch(request(['--cwd', self.tmp, 'commit', '-A', '-u', username, '-m', "hgfs[symlink]: %s -> %s" % (_target, source), str(source), str(_target)]))
#        if self.args.clone: dispatch(request(['--cwd', self.tmp, 'push']))
#
#        return status

    # FIXME: You have to have this here, otherwise, fusepy won't call your
    # truncate with the fh set. This causes certain cases to fail where a file
    # was opened with write, but mode set to 0000. In that case you should NOT
    # be able to reopen the file, but you SHOULD be able to truncate the
    # existing handle. See iozone sanity check.
    def ftruncate(self, path, length, fh):
        pass

    def truncate(self, path, length, fh=None):
        (parent, key, doc) = self._p2d(path)

        if isinstance(doc, basestring):
            parent[key] = u'' 
        elif isinstance(doc, bool):
            parent[key] = False
        elif isinstance(doc, numbers.Number):
            parent[key] = 0
        elif isinstance(doc, type(None)):
            parent[key] = None

    def unlink(self, path):
        (parent, key, doc) = self._p2d(path)
        del parent[key]

        return 0

    def utimens(self, path, times=None):
        return os.utime(self.path, times)

    def write(self, path, data, offset, fh):
        (parent, key, doc) = self._p2d(path)

        if isinstance(doc, basestring):
            # If the doc is a string, assume all input is a string as well.
 
            # First, convert data back to original bytes.
            docdata = doc.encode('latin1')

            # Then compute new data with offset.
            docdata = docdata[:offset] + data + docdata[offset + len(data):]

            # Finally re-encode the data for storage in a unicode string.
            parent[key] = docdata.decode('latin1')

        elif isinstance(doc, (numbers.Number, bool, type(None))):
            try:
                converted = json.loads(data)
                self.log.debug("Converted data: %s (%s)" % (repr(converted), type(converted)))

                # Check that the type isn't changing.
                if not isinstance(converted, type(doc)):
                    raise FuseOSError(EINVAL)

                # Check that the type is valid for a leaf.
                if not isinstance(converted, (numbers.Number, bool, type(None))):
                    raise FuseOSError(EINVAL)
            except:
                raise FuseOSError(EINVAL)

            if offset == 0:
                # Simple replacement.
                parent[key] = converted
            else:
                # Append like operation.
                if isinstance(doc, bool):
                    parent[key] ^= converted
                elif isinstance(doc, numbers.Number):
                    parent[key] += converted
                elif isinstance(doc, type(None)):
                    parent[key] = converted

        return len(data)

if __name__ == '__main__':
    logging.basicConfig()

    parser = argparse.ArgumentParser(description='JsonFS')
    parser.add_argument('path', help='Path to JSON document.')
    parser.add_argument('mountpoint', help='Location of mount point.')

    parser.add_argument('-l', '--log', help='Set the log level.', action='store', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], default='ERROR')

    args = parser.parse_args()

    fuse = FUSE(JsonFS(args.path, args.mountpoint, args), args.mountpoint, foreground=True, nothreads=True)
