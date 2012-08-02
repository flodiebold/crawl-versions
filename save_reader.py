#!/usr/bin/env python

import struct
import zlib
import sys

class SaveFileError(Exception):
    def __init__(self, msg):
        super(SaveFileError, self).__init__(msg)

class Package(object):
    file_header = struct.Struct("<IBxxxI")
    package_magic = 0x53534344

    def __init__(self, filename):
        self.filename = filename
        self.directory = dict()
        self.f = None
        self.load()
        
    def _read_file_header(self):
        data = self.f.read(Package.file_header.size)
        if len(data) < Package.file_header.size:
            raise SaveFileError("not a crawl save file")
        return Package.file_header.unpack(data)

    def load(self):
        try:
            self.f = open(self.filename, "rb")
            (self.magic, self.version, start) = self._read_file_header()
            if self.magic != Package.package_magic:
                raise SaveFileError("not a crawl save file")
            self._read_directory(start, self.version)
        except:
            self.close()

    def _read_directory(self, start, version):
        if version != 1:
            raise SaveFileError("unsupported package version")

        rd = ChunkReader(self, start)
        def _read_entry():
            data = rd.read(1)
            if len(data):
                (l,) = struct.unpack("<B", data)
                name = rd.read(l)
                if len(name) < l:
                    raise SaveFileError("save file corrupted -- truncated directory")
                (start,) = struct.unpack("<I", rd.read(4))
                self.directory[name] = start
                return True
            else:
                return False
        
        while _read_entry(): pass
    
    def get(self, name):
        if name in self.directory:
            return ChunkReader(self, self.directory[name])
        else:
            return None

    def close(self):
        if self.f:
            self.f.close()
            self.f = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def read_chr_chunk(self):
        chr_chunk = self.get("chr")
        version = chr_chunk.read_format("BB")
        chr_chunk.read(4) # length of the remaining data
        if version >= (32, 13):
            chr_chunk.read(1) # format
        self.player_name = chr_chunk.read_byte_string()
        self.crawl_version = chr_chunk.read_byte_string()
        return (self.player_name, self.crawl_version)
        

class ChunkReader(object):
    block_header = struct.Struct("<II")

    def __init__(self, pkg, start):
        self.package = pkg
        self.first_block = start
        self.next_block = start
        self.block_left = 0
        self.offset = None
        self.zlib = zlib.decompressobj()
    
    def _read_block_header(self):
        data = self.package.f.read(ChunkReader.block_header.size)
        if len(data) < ChunkReader.block_header.size:
            raise SaveFileError("save file corrupted -- block past eof")
        return ChunkReader.block_header.unpack(data)

    def _raw_read(self, l):
        data = bytes()
        while l:
            if self.block_left:
                self.package.f.seek(self.offset)
            else:
                if self.next_block:
                    self.package.f.seek(self.next_block)
                    self.offset = self.next_block + ChunkReader.block_header.size
                    (self.block_left, self.next_block) = self._read_block_header()
                else:
                    return data

            s = min(l, self.block_left)
            read = self.package.f.read(s)
            if len(read) < s:
                raise SaveFileError("save file corrupted -- block past eof")

            data += read
            self.offset += s
            l -= s
            self.block_left -= s

        return data
    
    def read(self, l):
        decompressed = bytes()
        while len(decompressed) < l:
            if self.zlib.unconsumed_tail:
                decompressed += self.zlib.decompress(self.zlib.unconsumed_tail, l - len(decompressed))
            else:
                data = self._raw_read(1024)
                decompressed += self.zlib.decompress(data, l - len(decompressed))
                if len(data) < 1024:
                    return decompressed
        return decompressed
    
    def read_all(self):
        data = bytes()
        more = True
        while more:
            new_data = self.read(1024)
            if len(new_data) < 1024: more = False
            data += new_data
        return data

    def read_format(self, fmt):
        size = struct.calcsize(fmt)
        data = self.read(size)
        if len(data) < size:
            raise SaveFileError("not enough data")
        return struct.unpack(fmt, data)

    def read_byte_string(self):
        (l,) = self.read_format("!h")
        if l < 0: raise SaveFileError("negative string length")
        result = self.read(l)
        if len(result) < l:
            raise SaveFileError("string beyond data")
        return result

if __name__ == "__main__":
    p = Package(sys.argv[1])
    print p.read_chr_chunk()[1]
