# Overview
This is the repository of my bachelors project

## How to run?

### Initialize and Update Submodules

First, clone the repository: 

```bash
git clone --recursive https://github.com/danieldraghici/Lucrare_Licenta.git
```

### Configure the environment
To set up the environment, run the following commands: 
```bash
cd Lucrare_Licenta/hailo-rpi5-examples
./install.sh
source setup_env.sh
cd ..
```

If you already have a configured environment, simply activate it:

```bash
cd Lucrare_Licenta/hailo-rpi5-examples
source setup_env.sh
cd ..
```

#### Python interpreter

Before running the project, make sure your IDE (e.g., VSCode or PyCharm) uses the Python interpreter from the virtual environment created during setup.
Select the following interpreter path:
```bash
hailo-rpi5-examples/venv_hailo_rpi5_examples/bin/python3.11
```

This ensures compatibility with the dependencies installed during setup.

## Running the project

### Running the autonomous vehicle pipeline

To use the custom pipeline, simply run the active debug configuration, after connecting to the RaspberryPi via SSH in VSCode

### Running the dashboard

The dashboard needs to be running on the host PC

The ports used in the pipeline (5000,4956) need to be exposed on the Raspberry Pi with VSCode

## Possible issues

### If at any point during the configuration, you encounter errors such as

**ninja: error: loading 'build.ninja': no such file or directory**

Try reinstalling meson

```bash
sudo apt-get install --reinstall meson
```
