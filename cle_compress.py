# Tool to compress (and encrypt) ED9_2 / Kuro no Kiseki 2 assets for Kuro 2 CLE.
# Usage:  Run by itself without commandline arguments and it will compress all files in the folder.
# For command line options (including option to dump vertices), run:
# /path/to/python3 kuro2_compress.py --help
#
# Requires zstandard for CLE assets.
# These can be installed by:
# /path/to/python3 -m pip install zstandard
#
# GitHub eArmada8/misc_kiseki

# Thank you to authors of Kuro Tools for the encryption and compression functions
# https://github.com/nnguyen259/KuroTools

try:
    import blowfish, zstandard, struct, operator, shutil, os, sys, glob
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

key = b"\x16\x4B\x7D\x0F\x4F\xA7\x4C\xAC\xD3\x7A\x06\xD9\xF8\x6D\x20\x94"
IV = b"\x9D\x8F\x9D\xA1\x49\x60\xCC\x4C"
iv = struct.unpack(">Q", IV)

def compressCLE(file_content):
    magic = file_content[0:4]
    result = file_content
    compressor = zstandard.ZstdCompressor(level = 9, write_checksum = True)
    result = compressor.compress(file_content)
    while (len(result) % 8) > 0:
        result += b'\x00'
    result = b"D9BA" + struct.pack("<I", len(result)) + result
    return result

def encryptCLE(file_content):
    cipher = blowfish.Cipher(key, byte_order = "big")
    dec_counter = blowfish.ctr_counter(iv[0], f = operator.add)
    result = b"".join(cipher.encrypt_ctr(file_content, dec_counter))
    while (len(result) % 8) > 0:
        result += b'\x00'
    result = b"F9BA" + struct.pack("<I", len(result)) + result
    return result

def processfile(filename):
    with open(filename, "rb") as f:
        file_content = f.read()
    print("Processing {0}...".format(filename))
    skip_magic = [b"D9BA", b"F9BA", b"C9BA"]
    if not file_content[0:4] in skip_magic: # Don't process files that are already CLE format:
        new_file_content = compressCLE(file_content)
        if not filename.split('.')[-1] in ['mdl','dds']:
            new_file_content = encryptCLE(new_file_content)
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
