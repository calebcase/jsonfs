jsonfs
======

JSON FS

A FUSE filesystem driver for mounting JSON documents.

**WARNING**
This code is experimental on a good day... on most days it will casually eat your data.

JSON to filesystem Mapping
--------------------------

::

 JSON      filesystem   user.json.type

 string => file      => string
 number => file      => number
 object => directory => object
 array  => directory => array
 true   => file      => boolean
 false  => file      => boolean
 null   => file      => null

All filesystem entries support the xattr 'user.json.type' (e.g. user.json.type = 'string') which indicates the JSON type of the filesystem entry. In this way, the JSON type is preserved.

The number type supports the additional xattr 'user.json.number.type' which indicates either 'integral' or 'real' number type.

File Creation
-------------

The default type of new files is 'string'.

Directory Creation
------------------

The default type of new directories is 'object'.

File Truncation
---------------

::

 string  => Empty string.
 number  => 0
 boolean => false
 null    => null

File Appending
--------------

::

 string  => Append to the end of the string.
 number  => Summation of existing number and new number.
 boolean => XOR of existing boolean and new boolean.
 null    => Always equals null.

Type Conversion
---------------

The user.json.type and user.json.number.type xattr's can be set (for example, by using the setfattr tool). An attempt will be made to convert from the existing type to the new type. All types are convertable to string via JSON serialize.

Array Handling
--------------

An array doesn't fit neatly into the directory/file world. Arrays are handled as special directories with entries named after their position in the array. Attempting to create an entry greater than the maximum index will result in empty files/directories for all the intervening indices. Removing an index in the middle of the array will result in the remaining entries being shift down one index. Attempts to create entries with negative index values will fail.
