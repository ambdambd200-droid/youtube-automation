"""Validate YAML workflow files."""
import yaml

for f in ['.github/workflows/daily_short.yml', '.github/workflows/weekly_long.yml']:
    try:
        with open(f, 'r') as fh:
            data = yaml.safe_load(fh)
        print(f'{f}: VALID')
        print(f'  Name: {data.get("name")}')
        print(f'  On: {list(data.get("on", {}).keys())}')
        print(f'  Jobs: {list(data.get("jobs", {}).keys())}')
    except Exception as ex:
        print(f'{f}: INVALID - {ex}')
