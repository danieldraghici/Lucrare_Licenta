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

To use the custom pipeline, simply run the python file but only after it's activate

```bash
python custom_pipeline.py
```

## Possible issues

### If at any point during the configuration, you encounter errors such as

**ninja: error: loading 'build.ninja': no such file or directory**

Try reinstalling meson

```bash
sudo apt-get install --reinstall meson
```
