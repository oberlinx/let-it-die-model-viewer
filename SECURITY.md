# Security Policy

## What this project is

A static website: plain HTML pages, pictures, sounds and data files. There are no accounts, no forms that send anything, no cookies and no tracking. The only request to another site is the [three.js](https://threejs.org/) library, downloaded from cdnjs the first time you open a 3D view.

The Python scripts in `tools/` are what built the site's data from the game files. They are not part of the website and only run if you run them yourself.

## Reporting a vulnerability

If you find something that could harm a visitor (for example a way a link to the site could run someone else's code in the page, or a tool that could damage game files), please **do not open a public issue**.

Report it privately through GitHub: go to the **Security** tab of the repository and choose **Report a vulnerability**
(https://github.com/oberlinx/let-it-die-model-viewer/security/advisories/new).

Please include what you found, how to reproduce it, and which browser and which version of the site (the date of the latest commit on GitHub) you tested.

You can expect an answer within about a week. This is a hobby project run by one person, so fixes may take longer, but real problems will be taken seriously and you will be credited if you want.

## Supported versions

Only the current version on the `main` branch and the live site at https://oberlinx.github.io/let-it-die-model-viewer/ are supported.

## Not a security issue

A wrong number, a missing picture or a page that doesn't display properly is a **bug** or a **data correction**, not a vulnerability. Please use those forms instead.
