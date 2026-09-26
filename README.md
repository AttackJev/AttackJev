# JevAdvBench

**A Benchmark and Black-Box Attacks for Reinforcement Learning for Calibrated Decisions Models**

Jianyi Hu\*, Hangtao Zhang\*, Yi Liu†, Yeqi Zeng, Li Zeng, Xianlong Wang, Rui Wang†, Leo Yu Zhang
<sub>\* Equal contribution · † Corresponding authors</sub>

🌐 **Project page:** https://jevadvbench.github.io/JevAdvBench/

JevAdvBench is, to our knowledge, the first adversarial benchmark for RLCD typed decision models:
812 typed questions over 66 scenarios and a black-box attack suite of 9,744 single-edit variants,
with delivery verified from billed input tokens. On `jev-1.13.0`, one unverified opinion appended to
the state flips 12.1% of decisions, statistically tied with the strongest injected command (10.1%),
and pushes 38% of confident answers below the 0.8 confidence gate that routes them to human review.

## Citation

```bibtex
@misc{hu2026jevadvbench,
  title  = {JevAdvBench: A Benchmark and Black-Box Attacks for
            Reinforcement Learning for Calibrated Decisions Models},
  author = {Hu, Jianyi and Zhang, Hangtao and Liu, Yi and Zeng, Yeqi and
            Zeng, Li and Wang, Xianlong and Wang, Rui and Zhang, Leo Yu},
  year   = {2026},
  note   = {Preprint}
}
```

The site source lives in [`docs/`](docs/) and is deployed to GitHub Pages by
[`.github/workflows/pages.yml`](.github/workflows/pages.yml) on every push to `main`.
