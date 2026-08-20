# Tool to decompress files compressed with lz4.
# Usage:  Run by itself without commandline arguments and it will decompress all files compressed with lz4.
#
# For command line options , run:
# /path/to/python3 lz4_decompress.py --help
#
# Requires the lz4 library to run.
# This can be installed by:
# /path/to/python3 -m pip install lz4
#
# GitHub eArmada8/kuro_mdl_tool

try:
    import lz4.frame, shutil, glob, os, sys
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

def decompress_lz4_file (lz4_filename):
    if os.path.exists(lz4_filename):
        cmp_data = open(lz4_filename, 'rb').read()
        if cmp_data[0:4] == b'\x04\x22\x4D\x18':
            unc_data = lz4.frame.decompress(cmp_data)
            shutil.copy2(lz4_filename, lz4_filename + '.compressed_original')
            open(lz4_filename, 'wb').write(unc_data)
    return

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
        parser.add_argument('lz4_filename', help="Name of file compressed with lz4 (required).")
        args = parser.parse_args()
        if os.path.exists(args.lz4_filename):
            decompress_lz4_file(args.lz4_filename)
    else:
        all_files = [x for x in glob.glob('*.*') if not '.compressed_original' in x and not '.py' in x]
        for i in range(len(all_files)):
            decompress_lz4_file(all_files[i])
