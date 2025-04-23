# Horse Racing Prediction Program

This repository contains a horse racing prediction program that collects and analyzes data from netkeiba.com to identify value betting opportunities.

## Information Gathering Component

The information gathering component is responsible for collecting all the required data points from netkeiba.com as specified in `docs/searchlist.md`. It uses a combination of BeautifulSoup for static content and Selenium for dynamic content.

### Dependencies

- Python 3.x
- requests
- beautifulsoup4
- selenium
- webdriver-manager

Install dependencies:

```bash
pip install requests beautifulsoup4 selenium webdriver-manager
```

### Usage

```bash
python main.py <race_id>
```

Example:

```bash
python main.py 202306050811
```

### Testing Without Selenium

If you encounter issues with Selenium or Chrome in your environment, you can use the `test_non_selenium.py` script to test the non-Selenium parts of the implementation:

```bash
python test_non_selenium.py <race_id>
```

This script will skip the Selenium-dependent parts (paddock information, speed figures, race announcements, and live odds) but will still collect basic race information, horse details, jockey profiles, trainer profiles, and pedigree data.

## Data Categories

The system collects data across several categories:

- **A. Race Conditions**: Basic race info, course characteristics, weather, track conditions
- **B. Horse Details**: Basic attributes, past results, pedigree, training info, condition
- **C. Human Factors**: Jockey and trainer information
- **D. Market Information**: Odds and payouts

## Validation

The system includes a validation component that ensures all required data points are collected. The validation report is saved as `validation_report_<race_id>.json`.
