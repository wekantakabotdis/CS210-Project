# CS210-Project

This project builds a master Pokemon card pricing dataset for the CS 210 project.
The dataset is created from TCGCSV's public Pokemon group, product, and price endpoints.

## Files

- `import_pokemon_dataset.py`: downloads the data and builds the master CSV
- `main.ipynb`: notebook version for running or previewing the import
- `data/pokemon_card_price_dataset.csv`: output CSV created by the Python script

## Requirements

Use Python 3 with these packages installed:

```bash
pip install pandas requests
```

## How To Run

From the `CS210-Project` folder, run:

```bash
python3 import_pokemon_dataset.py
```

The script will:

- fetch all Pokemon groups from TCGCSV
- fetch each group's products and prices
- keep Pokemon card rows with usable card attributes
- build one master dataset
- save the final CSV to `data/pokemon_card_price_dataset.csv`

## Output

After the script finishes, the master dataset will be here:

```bash
data/pokemon_card_price_dataset.csv
```

## Notes

- The import may take a little time because it walks through all groups one by one.
- The script prints progress as each group is processed.
- The notebook `main.ipynb` can also run the import, but the Python script is the simplest way to generate the dataset again.
