# Codec for Rome Total War Remastered's music files

## Description

A reverse-engineered codec for Rome Total War Remastered's music files
- Unpack and repack RTW:RE's music files
- Modification of existing tracks
- No possibility of adding new tracks for now

## Usage

```
# Rebuild the music.dat and music.idx files from the opus files in input_path. Resulting binary files are located in output_path.
codec.py --rebuild --input $input_path --output $output_path
# Extract the music tracks from the music.dat and music.idx in input_path. Resulting opus files are located in output_path.
codec.py --extract --input $input_path --output $output_path
```
