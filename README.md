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
cd hailo-rpi5/hailo-rpi5-examples
source setup_env.sh
pip install -r requirements.txt
./download_resources.sh
./compile_postprocess.sh
cd ..
```

If you already have a configured environment, simply activate it:

```bash
cd hailo-rpi5/hailo-rpi5-examples
source setup_env.sh
cd ..
```
