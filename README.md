# EELVault

A curated collection of hand-crafted EEL2 DSP scripts for RootlessJamesDSP and JDSP4Linux.

Each script in this collection is designed, tested, and documented as a complete audio processor. These are not templates or fragments. They are finished, loadable `.eel` files ready for deployment.

## Collection Index

| # | Name | Type | Status |
|---|------|------|--------|
| 1 | [ANIMA](dsp/anima/) | Vintage Harmonic Engine | Stable |
| 2 | [SoloConsole](dsp/soloconsole/) | Oversampled Console Drive | Experimental |

## How to Use

1. Open the `dsp/` directory.
2. Choose a processor folder.
3. Read its `README.md` for the signal flow, parameters, and installation instructions.
4. Copy the `.eel` file to your RootlessJamesDSP or JDSP4Linux liveprog directory.
5. Enable the Liveprog effect and select the script.

## Repository Structure

```
EELVault/
├── docs/          # Guides and references
├── dsp/           # One folder per DSP script
│   ├── anima/     # ANIMA (vintage harmonic engine)
│   └── soloconsole/  # SoloConsole (oversampled console drive)
├── templates/     # Templates for adding new DSP entries
└── assets/        # Logos, images, branding
```

## Adding a New DSP

1. Copy the templates from `templates/`.
2. Create a new folder under `dsp/` using the lowercase name of your DSP.
3. Fill in the README, metadata, and CHANGELOG.
4. Place your `.eel` file in the folder.
5. Update the Collection Index table in this README.

## Built With

- [EELForge](https://github.com/) — Prompt workbench for designing EEL2 DSP scripts
- [RootlessJamesDSP](https://github.com/Audio4Linux/RootlessJamesDSP) — Android DSP engine
- [JDSP4Linux](https://github.com/Audio4Linux/JDSP4Linux) — Linux DSP engine

## License

See [LICENSE](LICENSE).