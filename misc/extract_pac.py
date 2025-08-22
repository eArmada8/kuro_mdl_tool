# GitHub eArmada8/kuro_mdl_tool

import struct, glob, os, sys

def read_null_terminated_string (f, start_offset):
    current_loc = f.tell()
    f.seek(start_offset)
    null_term_string = f.read(1)
    while null_term_string[-1] != 0:
        null_term_string += f.read(1)
    f.seek(current_loc)
    return(null_term_string[:-1].decode())

def process_pac (pac_file):
    print("Processing {}...".format(pac_file))
    with open(pac_file, 'rb') as f:
        magic = f.read(4)
        if magic == b'FPAC':
            count, header_size, unk = struct.unpack("<3I", f.read(12))
            files = []
            for i in range(count):
                entry_dat = struct.unpack("<4Q", f.read(32))
                files.append({'name': read_null_terminated_string (f, entry_dat[1]),
                    'location': entry_dat[3],
                    'size': entry_dat[2],
                    'hash': entry_dat[0]})
            for i in range(count):
                f.seek(files[i]['location'])
                f_data = f.read(files[i]['size'])
                filedir = os.path.dirname(files[i]['name'])
                if not filedir == '' and not os.path.exists(filedir):
                    os.makedirs(filedir)
                with open(files[i]['name'], 'wb') as f2:
                    f2.write(f_data)
    return

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to extract from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('pac_filename', help="Name of pac file to extract from (required).")
        args = parser.parse_args()
        if os.path.exists(args.pac_filename) and args.pac_filename[-4:].lower() == '.pac':
            process_pac(args.pac_filename)
    else:
        pac_files = glob.glob('*.pac')
        for i in range(len(pac_files)):
            process_pac(pac_files[i])
