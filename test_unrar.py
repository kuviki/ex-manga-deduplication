import rarfile
import os

def extract_rar(rar_path, extract_path):
    if not os.path.exists(extract_path):
        os.makedirs(extract_path)
    
    try:
        with rarfile.RarFile(rar_path) as rf:
            rf.extractall(extract_path)
        print(f"Successfully extracted {rar_path} to {extract_path}")
    except rarfile.Error as e:
        print(f"Error extracting RAR file: {e}")
    except FileNotFoundError:
        print(f"Error: RAR file not found at {rar_path}")

if __name__ == "__main__":
    rar_file = "test.rar"
    output_directory = "test"
    extract_rar(rar_file, output_directory)