# Decode the binary JSON format seen in PS4 / NX versions of the
# FDK engine games.  Outputs text JSON format.
#
# GitHub eArmada8/kuro_mdl_tool

import struct, json, glob, os, sys

def read_null_terminated_string (f):
    str_bin = f.read(1)
    while str_bin[-1] != 0:
        str_bin += f.read(1)
    return(str_bin[:-1].decode('utf-8'))

def read_string_from_dict (f):
    addr, = struct.unpack("<I", f.read(4))
    return_address = f.tell()
    f.seek(addr)
    f.seek(4,1) # unknown, maybe a hash?
    dict_string = read_null_terminated_string(f)
    f.seek(return_address)
    return(dict_string)

def read_value (f):
    dat_type, = struct.unpack("<B", f.read(1))
    name = ''
    if dat_type < 0x10:
        name = read_string_from_dict(f)
    else:
        name = ''
    if dat_type in [0x02, 0x12]:
        data = read_null_terminated_string(f)
    elif dat_type in [0x03, 0x13]:
        data, = struct.unpack("<d", f.read(8))
    elif dat_type in [0x04, 0x14]:
        data = {}
        num_entries, = struct.unpack("<I", f.read(4))
        f.seek(4 * num_entries, 1) # These are the byte locations of the entries, unneeded (and out of order)
        for _ in range(num_entries):
            datum = read_value(f)
            data[datum[0]] = datum[1]
    elif dat_type in [0x05, 0x15]:
        data = []
        num_entries, = struct.unpack("<I", f.read(4))
        f.seek(4 * num_entries, 1) # These are the byte locations of the entries, unneeded
        for _ in range(num_entries):
            datum = read_value(f)
            data.append(datum[1])
    elif dat_type in [0x06, 0x16]:
        data = {0:False, 1:True}[struct.unpack("<B", f.read(1))[0]]
    else:
        print("Unknown OP code!! code {0}, location: {1}.".format(hex(dat_type), hex(f.tell()-1)))
    return(name, data)

def decode_falcom_bin_json (bin_json_filename, overwrite = False):
    print("Processing {}...".format(bin_json_filename))
    with open(bin_json_filename, 'rb') as f:
        f.seek(0,2)
        eof = f.tell()
        f.seek(0)
        magic = f.read(4)
        if magic == b'JSON':
            f.seek(4,1) #unk
            dat_start, = struct.unpack("<I", f.read(4))
            f.seek(dat_start)
            name, data = read_value(f) # the first name seems to always be blank, so will be discarded
            json_filename = bin_json_filename.split('.mi')[0] + '.json'
            if os.path.exists(json_filename) and (overwrite == False):
                if str(input(json_filename + " exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                    overwrite = True
            if (overwrite == True) or not os.path.exists(json_filename):
                with open(json_filename, 'wb') as ff:
                    ff.write(json.dumps(data, indent = 4).encode('utf-8'))
            if not f.tell() == eof:
                print("Warning!  End of file not reached, there may be more data.")
                print("Location: {0}, EOF: {1}.".format(f.tell(), eof))
                input("Press Enter to continue.")
        else:
            print("{0} is not an FDK binary JSON, skipping...".format(bin_json_filename))

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('bin_json_filename', help="Name of .mi file to export from (required).")
        args = parser.parse_args()
        if os.path.exists(args.bin_json_filename):
            decode_falcom_bin_json(args.bin_json_filename, overwrite = args.overwrite)
    else:
        bin_json_files = glob.glob('*.mi')
        for i in range(len(bin_json_files)):
            decode_falcom_bin_json(bin_json_files[i])