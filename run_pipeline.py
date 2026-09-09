import subprocess
import sys
import os

def run_cmd(args, cwd=None):
    print(f"Running: {' '.join(args)}")
    res = subprocess.run(args, cwd=cwd)
    if res.returncode != 0:
        print(f"Error executing command: {' '.join(args)}")
        sys.exit(res.returncode)

def main():
    # Make sure we use the virtual environment python
    venv_python = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = "python" # fallback
        
    print("=== STEP 1: Running Synthetic Data Generator ===")
    run_cmd([venv_python, "data_generator/generate_data.py", "--users", "1000", "--txs", "10000"])
    
    print("\n=== STEP 2: Running Structuring (Smurfing) Detection Rule ===")
    run_cmd([venv_python, "detection/detect_structuring.py"])
    
    print("\n=== STEP 3: Running Graph-Based Money Mule Network Detection ===")
    run_cmd([venv_python, "detection/detect_mule_networks.py"])
    
    print("\n=== Pipeline Complete! All CSVs and subgraphs are generated. ===")
    
if __name__ == "__main__":
    main()
