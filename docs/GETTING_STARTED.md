# Getting Started with EELVault

## Prerequisites

- RootlessJamesDSP (Android) or JDSP4Linux (Linux desktop)
- A text editor for reading documentation
- A file manager or terminal for copying `.eel` files

## Installing a DSP Script

### RootlessJamesDSP (Android)

1. Open RootlessJamesDSP.
2. Navigate to the Liveprog section.
3. Copy the desired `.eel` file to the Liveprog scripts directory.
4. Enable the Liveprog effect.
5. Select the script from the dropdown.

### JDSP4Linux (Linux Desktop)

1. Copy the desired `.eel` file to your preferred scripts directory.
2. Open JDSP4Linux.
3. Enable the Liveprog effect.
4. Set the `liveprog_file` path to your `.eel` file.
5. Or use the CLI:
   ```bash
   jamesdsp --set liveprog_enable=true
   jamesdsp --set 'liveprog_file=/path/to/anima.eel'
   ```

## Verifying Installation

After loading a script, play audio through your system. If the script loads correctly, you will hear the processing. If the script fails to load, check the JamesDSP logs for syntax errors.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No audio | Script syntax error | Check the `desc:` line is the first line. Ensure `@init` and `@sample` sections exist. |
| Muted audio | Uninitialized memory or limiter collapse | Ensure all delay buffers are zeroed in `@init`. Check limiter gain computer. |
| Clicks/pops | Reading uninitialized delay buffer | Ensure the delay buffer is cleared before first read. Use `loop()` not `while()` for buffer clearing. |
| Script not appearing | Wrong file path or extension | Ensure the file has a `.eel` extension and the path is correct. |