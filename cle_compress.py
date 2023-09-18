# Tool to compress ED9_@ / Kuro no Kiseki 2 assets for Kuro 2 CLE.
# Usage:  Run by itself without commandline arguments and it will compress all files in the folder.
# For command line options (including option to dump vertices), run:
# /path/to/python3 kuro2_compress.py --help
#
# Requires zstandard for CLE assets.
# These can be installed by:
# /path/to/python3 -m pip install zstandard
#
# GitHub eArmada8/misc_kiseki

# Thank you to authors of Kuro Tools for this decrypt function
# https://github.com/nnguyen259/KuroTools

try:
    import zstandard, struct, shutil, os, sys, glob
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def compressCLE(file_content):
    magic = file_content[0:4]
    compressed_magic = b"D9BA"
    result = file_content
    if not magic == compressed_magic: # Don't compress files that are already compressed:
        compressor = zstandard.ZstdCompressor(level = 12, write_checksum = True)
        result = compressor.compress(file_content)
        while (len(result) % 8) > 0:
            result += b'\x00'
        result = compressed_magic + struct.pack("<I", len(result)) + result
    return result

def processfile(filename):
    with open(filename, "rb") as f:
        file_content = f.read()
    print("Processing {0}...".format(filename))
    new_file_content = compressCLE(file_content)
    if not new_file_content == file_content: # Do not process if file is unchanged
        # Instead of overwriting backups, it will just tag a number onto the end
        backup_suffix = ''
        if os.path.exists(filename + '.bak' + backup_suffix):
            backup_suffix = '1'
            if os.path.exists(filename + '.bak' + backup_suffix):
                while os.path.exists(filename + '.bak' + backup_suffix):
                    backup_suffix = str(int(backup_suffix) + 1)
            shutil.copy2(filename, filename + '.bak' + backup_suffix)
        else:
            shutil.copy2(filename, filename + '.bak')
        with open(filename,'wb') as f:
            f.write(new_file_content)

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
        parser.add_argument('filename', help="Name of file to compress.")
        args = parser.parse_args()
        if os.path.exists(args.filename):
            processfile(args.filename)
    else:
        files = glob.glob('*.*')
        files = [x for x in files if not (('.py' in x) or ('.bak' in x))]
        for i in range(len(files)):
            processfile(files[i])
