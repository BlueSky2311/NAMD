import os
import subprocess
import fileinput
import shutil
import pandas as pd
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def download_and_extract(jobid):
    # Download the CHARMM-GUI files
    download_cmd = f"curl 'https://www.charmm-gui.org/?doc=input/download&jobid={jobid}' --output charmm-gui.tgz --compressed"
    os.system(download_cmd)

    # Extract the CHARMM-GUI files
    extract_cmd = "tar -zxf charmm-gui.tgz"
    os.system(extract_cmd)

    # Define the name of the extracted folder
    extracted_folder = f"charmm-gui-{jobid}"

    # Remove the downloaded .tgz file
    os.remove("charmm-gui.tgz")

    return extracted_folder

def run_equilibration(folder):
    file_path = Path(f"/content/drive/MyDrive/namd/{folder}/namd")
    os.chdir(file_path)

    if not check_log_file(file_path, './step4_equilibration.log'):
        # Run the NAMD equilibration
        command = f"/content/NAMD_3.0b6_Linux-x86_64-multicore-CUDA/namd3 +auto-provision +idlepoll +devices 0 ./step4_equilibration.inp"
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Write the output to the log file
        with open('./step4_equilibration.log', 'wb') as f:
            f.write(process.stdout)

def run_simulation(folder):
    file_path = Path(f"/content/drive/MyDrive/namd/{folder}/namd")
    os.chdir(file_path)

    check_and_modify(file_path, "step5_simulation.inp")

    if not check_log_file(file_path, "step5_simulation.inp"):
        # Run the NAMD simulation
        command = f"/content/NAMD_3.0b6_Linux-x86_64-multicore-CUDA/namd3 +auto-provision +idlepoll +devices 0 ./step5_simulation.inp"
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Get the output name from the input file
        with open(file_path / "step5_simulation.inp", 'r') as f:
            for line in f:
                if "outputName" in line:
                    output_name = line.split()[1]
                    break

        log_file = file_path / f"{output_name}.log"

        # Write the output to the log file
        with open(log_file, 'wb') as f:
            f.write(process.stdout)

def check_log_file(file_path, log_file):
    with open(file_path / log_file, 'rb') as f:
        content = f.read()
        return b'End of program' in content

def check_and_modify(file_path, inp_file):
    # Get the output name from the input file
    with open(file_path / inp_file, 'r') as f:
        for line in f:
            if "outputName" in line:
                output_name = line.split()[1]
                break

    log_file = f"{output_name}.log"

    try:
        with open(file_path / log_file, 'r') as f:
            content = f.read()
            if 'End of program' in content:
                pass  # File exists and completed, no modification needed
            else:
                # File exists but not completed, modify the run steps
                xsc_file = f"{output_name}.restart.xsc"
                with open(file_path / xsc_file, 'r') as f:
                    for line in f:
                        if line.startswith('#$LABELS'):
                            continue
                        else:
                            step_value = int(line.split()[0])
                            break

                with fileinput.FileInput(file_path / inp_file, inplace=True) as file:
                    for line in file:
                        if "numsteps" in line:
                            print(f"numsteps               50000000;")
                        elif "run" in line:
                            print(f"run                    {50000000 - step_value};")
                        else:
                            print(line.rstrip())

                # Modify other lines for resuming the production run
                with fileinput.FileInput(file_path / inp_file, inplace=True) as file:
                    for line in file:
                        if "outputName              step5_production;" in line:
                            print("outputName              step5_production2;")
                        elif "set inputname           step4_equilibration;" in line:
                            print("set inputname           step5_production;")
                        elif "binCoordinates          $inputname.coor;" in line:
                            print("binCoordinates          $inputname.restart.coor;")
                        elif "binVelocities           $inputname.vel;" in line:
                            print("binVelocities           $inputname.restart.vel;")
                        elif "extendedSystem          $inputname.xsc;" in line:
                            print("extendedSystem          $inputname.restart.xsc;")
                        else:
                            print(line.rstrip())

    except FileNotFoundError:
        # File doesn't exist, modify the run steps for the first run
        with fileinput.FileInput(file_path / inp_file, inplace=True) as file:
            for line in file:
                if "numsteps" in line:
                    print("numsteps               50000000;")
                elif "run" in line:
                    print("run                    50000000;")
                else:
                    print(line.rstrip())

    # Check for a different output name if the log file exists
    try:
        with open(file_path / log_file, 'r') as f:
            pass  # File exists, check for a different output name
    except FileNotFoundError:
        pass  # File doesn't exist, no modification needed
    else:
        # File exists, check for a different output name
        counter = 2
        while True:
            new_output_name = f"{output_name}{counter}"
            new_log_file = f"{new_output_name}.log"
            try:
                with open(file_path / new_log_file, 'r') as f:
                    pass  # File exists, try the next counter
            except FileNotFoundError:
                # Modify the input file
                with fileinput.FileInput(file_path / inp_file, inplace=True) as file:
                    for line in file:
                        if "outputName" in line:
                            print(f"outputName              {new_output_name};")
                        else:
                            print(line.rstrip())
                break
            counter += 1

if __name__ == "__main__":
    # Download the NAMD
    namd_download_cmd = "wget https://www.ks.uiuc.edu/Research/namd/3.0b6/download/120834/NAMD_3.0b6_Linux-x86_64-multicore-CUDA.tar.gz"
    os.system(namd_download_cmd)

    # Extract NAMD
    namd_extract_cmd = "tar -zxf NAMD_3.0b6_Linux-x86_64-multicore-CUDA.tar.gz"
    os.system(namd_extract_cmd)

    # Load the CSV file
    df = pd.read_csv('/content/test.csv')

    # Get the jobids from the first column
    jobids = df.iloc[:, 0].tolist()

    # Download, extract, and move the CHARMM-GUI files
    extracted_folders = []
    for jobid in jobids:
        extracted_folder = download_and_extract(jobid)
        extracted_folders.append(extracted_folder)

        # Move the extracted folder to /content/drive/MyDrive/namd
        shutil.move(extracted_folder, f"/content/drive/MyDrive/namd/{extracted_folder}")

    # Run equilibration and simulation one by one in each folder
    for folder in extracted_folders:
        run_equilibration(folder)
        run_simulation(folder)