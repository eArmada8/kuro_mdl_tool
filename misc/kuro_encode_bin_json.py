# Encode the binary JSON format seen in PS4 / NX versions of the
# FDK engine games.  Outputs binary JSON format.
#
# GitHub eArmada8/kuro_mdl_tool

try:
    import zlib, io, struct, json, re, glob, os, sys
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

class bin_json_writer:
    def __init__(self):
        self.f = None
        self.str_dict = {} # Dictionary words -> binary location

    def write_null_terminated_string (self, string, add_crc = False):
        encoded_string = string.encode('utf-8')
        if add_crc == True:
            self.f.write(struct.pack("<I", int("0b"+"1"*32, 2) - zlib.crc32(encoded_string)))
        self.f.write(encoded_string)
        self.f.write(b'\x00')
        return

    def write_dict_value (self, data):
        if data == None:
            pass
        elif isinstance(data, str):
            pass
        elif isinstance(data, bool):
            pass
        elif isinstance(data, int) or isinstance(data, float):
            pass
        elif isinstance(data, dict):
            keys = list(data.keys())
            for key in keys:
                if key not in self.str_dict:
                    self.str_dict[key] = self.f.tell()
                    self.write_null_terminated_string(key, add_crc = True)
                self.write_dict_value(data[key])
        elif isinstance(data, list):
            for i in range(len(data)):
                self.write_dict_value(data[i])
        return

    def write_value (self, data):
        if data == None:
            pass
        elif isinstance(data, str):
            self.write_null_terminated_string(data, add_crc = False)
        elif isinstance(data, bool):
            self.f.write(struct.pack("<B", {False:0, True:1}[data]))
        elif isinstance(data, int) or isinstance(data, float):
            self.f.write(struct.pack("<d", float(data)))
        elif isinstance(data, dict):
            keys = list(data.keys())
            self.f.write(struct.pack("<I", len(keys)))
            block_start = self.f.tell()
            self.f.write(struct.pack("<{}I".format(len(keys)), *[0]*len(keys)))
            datum_block_starts = []
            for key in keys:
                datum_block_starts.append(self.f.tell())
                if data[key] == None:
                    self.f.write(struct.pack("<BI", 0x01, self.str_dict[key]))
                    self.write_value(data[key])
                elif isinstance(data[key], str):
                    self.f.write(struct.pack("<BI", 0x02, self.str_dict[key]))
                    self.write_value(data[key])
                elif isinstance(data[key], bool):
                    self.f.write(struct.pack("<BI", 0x06, self.str_dict[key]))
                    self.write_value(data[key])
                elif isinstance(data[key], int) or isinstance(data[key], float):
                    self.f.write(struct.pack("<BI", 0x03, self.str_dict[key]))
                    self.write_value(data[key])
                elif isinstance(data[key], dict):
                    self.f.write(struct.pack("<BI", 0x04, self.str_dict[key]))
                    self.write_value(data[key])
                elif isinstance(data[key], list):
                    self.f.write(struct.pack("<BI", 0x05, self.str_dict[key]))
                    self.write_value(data[key])
            block_end = self.f.tell()
            self.f.seek(block_start)
            self.f.write(struct.pack("<{}I".format(len(datum_block_starts)), *datum_block_starts))
            self.f.seek(block_end)
        elif isinstance(data, list):
            self.f.write(struct.pack("<I", len(data)))
            block_start = self.f.tell()
            self.f.write(struct.pack("<{}I".format(len(data)), *[0]*len(data)))
            datum_block_starts = []
            for i in range(len(data)):
                datum_block_starts.append(self.f.tell())
                if data[i] == None:
                    self.f.write(struct.pack("B", 0x11))
                    self.write_value(data[i])
                elif isinstance(data[i], str):
                    self.f.write(struct.pack("B", 0x12))
                    self.write_value(data[i])
                elif isinstance(data[i], bool):
                    self.f.write(struct.pack("B", 0x16))
                    self.write_value(data[i])
                elif isinstance(data[i], int) or isinstance(data[i], float):
                    self.f.write(struct.pack("B", 0x13))
                    self.write_value(data[i])
                elif isinstance(data[i], dict):
                    self.f.write(struct.pack("B", 0x14))
                    self.write_value(data[i])
                elif isinstance(data[i], list):
                    self.f.write(struct.pack("B", 0x15))
                    self.write_value(data[i])
            block_end = self.f.tell()
            self.f.seek(block_start)
            self.f.write(struct.pack("<{}I".format(len(datum_block_starts)), *datum_block_starts))
            self.f.seek(block_end)
        return

    def encode_bin_json (self, data):
        self.f = io.BytesIO()
        self.str_dict = {} # Clear dictionary
        # temporary value, the Q is the address of the start of struct
        self.f.write(b'JSON\x00\x00\x00\x00' + struct.pack("<Q", 0))
        # Add the blank string to the beginning of the dictionary
        self.str_dict[''] = self.f.tell()
        self.write_null_terminated_string('', add_crc = True)
        self.write_dict_value(data)
        data_start = self.f.tell()
        self.f.seek(8)
        self.f.write(struct.pack("<Q", data_start))
        self.f.seek(data_start)
        if data == None:
            self.f.write(struct.pack("<BI", 0x01, self.str_dict['']))
            self.write_value(data)
        elif isinstance(data, str):
            self.f.write(struct.pack("<BI", 0x02, self.str_dict['']))
            self.write_value(data)
        elif isinstance(data, int) or isinstance(data, float):
            self.f.write(struct.pack("<BI", 0x03, self.str_dict['']))
            self.write_value(data)
        elif isinstance(data, dict):
            self.f.write(struct.pack("<BI", 0x04, self.str_dict['']))
            self.write_value(data)
        elif isinstance(data, list):
            self.f.write(struct.pack("<BI", 0x05, self.str_dict['']))
            self.write_value(data)
        elif isinstance(data, bool):
            self.f.write(struct.pack("<BI", 0x06, self.str_dict['']))
            self.write_value(data)
        return

    def write_bin_json (self, json_filename, overwrite = False):
        if os.path.exists(json_filename):
            with open(json_filename, 'rb') as f2:
                data = json.loads(f2.read())
            self.encode_bin_json(data)
            self.f.seek(0)
            mi_filename = re.sub(".json", ".mi", json_filename, flags=re.IGNORECASE)
            if os.path.exists(mi_filename) and (overwrite == False):
                if str(input(mi_filename + " exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                    overwrite = True
            if (overwrite == True) or not os.path.exists(mi_filename):
                with open(mi_filename, 'wb') as f2:
                    f2.write(self.f.read())
            return

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    bin_json_writer = bin_json_writer()

    # If argument given, attempt to encode file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('json_filename', help="Name of json file to encode (required).")
        args = parser.parse_args()
        if os.path.exists(args.json_filename):
            bin_json_writer.write_bin_json(args.json_filename, overwrite = args.overwrite)
    else:
        json_files = glob.glob('*.json')
        for i in range(len(json_files)):
            bin_json_writer.write_bin_json(json_files[i])