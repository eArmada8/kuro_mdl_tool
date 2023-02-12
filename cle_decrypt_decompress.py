# Tool to decompress Kuro no Kiseki 1 and 2 assets from the CLE release
# Usage:  Run by itself without commandline arguments and it will decompress all files in the folder.
# For command line options, run:
# /path/to/python3 cle_decrypt_decompress.py --help
#
# Requires blowfish and zstandard for CLE assets.
# These can be installed by:
# /path/to/python3 -m pip install blowfish zstandard
#
# GitHub eArmada8/kuro_mdl_tool

# Thank you to authors of Kuro Tools for this decrypt function
# https://github.com/nnguyen259/KuroTools

import blowfish, struct, operator, zstandard, shutil, sys, os, glob

key = b"\x16\x4B\x7D\x0F\x4F\xA7\x4C\xAC\xD3\x7A\x06\xD9\xF8\x6D\x20\x94"
IV = b"\x9D\x8F\x9D\xA1\x49\x60\xCC\x4C"
cipher = blowfish.Cipher(key, byte_order = "big")
iv = struct.unpack(">Q", IV)
dec_counter = blowfish.ctr_counter(iv[0], f = operator.add)
to_decrypt = [b"F9BA", b"C9BA"]
to_decompress = [b"D9BA"]

def checkCLE (f):
    f.seek(0)
    if f.read(4) in to_decrypt+to_decompress:
        return True
    else:
        return False
    
def processCLE (f):
    f.seek(0)
    file_content = f.read()
    result = file_content
    while (file_content[0:4] in to_decrypt) or (file_content[0:4] in to_decompress):
        if (file_content[0:4] in to_decrypt):
            result = b"".join(cipher.decrypt_ctr(file_content[8:], dec_counter))
        elif(file_content[0:4] in to_decompress):
            decompressor = zstandard.ZstdDecompressor()
            result = decompressor.decompress(file_content[8:])
        file_content = result
    return result

def processFile(cle_asset_filename):
    processed_data = False
    with open(cle_asset_filename, 'rb') as f:
        if checkCLE(f) == True:
            processed_data = processCLE(f)
    if processed_data != False:
        # Make a backup
        shutil.copy2(cle_asset_filename, cle_asset_filename + '.original_encrypted')
        with open(cle_asset_filename, 'wb') as f:
            f.write(processed_data)
    return

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('cle_asset_filename', help="Name of file to decrypt / decompress (required).")
        args = parser.parse_args()
        if os.path.exists(args.cle_asset_filename):
            processFile(args.cle_asset_filename)
    else:
        all_files = [x for x in glob.glob('*.*', recursive = False)\
            if x not in glob.glob('*.original_encrypted', recursive = False)]
        for i in range(len(all_files)):
            processFile(all_files[i])