# JevAdvBench project page

This branch holds only the website served at https://jevadvbench.github.io/JevAdvBench/.
The paper, data and code live on [`main`](https://github.com/JevAdvBench/JevAdvBench).

- `index.html` is the whole site: one self-contained page (styles, data and charts inline;
  fonts from Google Fonts).
- Pushing to this branch publishes it automatically: `.github/workflows/publish.yml` triggers
  the deploy workflow on `main`, which checks out this branch and deploys it to GitHub Pages.

To preview locally, open `index.html` in a browser.
