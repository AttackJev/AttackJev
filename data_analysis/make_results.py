"""Regenerate every table in ../results from the restored evidence."""
import json
import flips
import effects
from common import RESULTS

if __name__ == "__main__":
    headline = {}
    headline.update(flips.main())
    headline.update(effects.main())
    (RESULTS / "headline.json").write_text(json.dumps(headline, indent=1) + "\n")
    print(f"Wrote {len(list(RESULTS.glob('*.csv')))} tables and headline.json to {RESULTS}")
