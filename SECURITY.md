# Security

CraftArenaBench calls endpoints run by strangers and publishes what comes back. If you find a way to turn that against the service or against another entrant, please tell us privately first.

## Reporting

Use GitHub's private vulnerability reporting on this repository ("Security" tab, "Report a vulnerability"), or email yogyamehrotra@gmail.com. Please don't open a public issue for anything that could be used against the service before it is fixed. We aim to acknowledge a report within a week; this is a volunteer project.

Things we would like to hear about:

- An endpoint response that crashes, stalls or misleads the harness, or makes the scoring job do anything other than play the match.
- A way to publish a rating the scoring service did not produce, or to publish one under another entry's name.
- A way for an endpoint to learn which opponent or seed it is facing, or to tell the house bot apart, from what the harness sends.
- A way to make the scoring job connect to anything other than the entrants' declared endpoints and PaperMC's download service.
- Anything on the website that runs script from another origin or shows content an entrant did not write.

## What is in place (planned; this file is updated as each piece lands)

- No entrant code runs on the scorer. The only thing an entrant controls is the JSON their endpoint returns, which is parsed with a strict schema and a size limit; anything else counts as a missing answer.
- Endpoint URLs must be `https://`. The harness follows no redirects, sends no credentials of its own, and only ever sends fight state.
- Everything the scoring job produces is checked against the repository by a separate job before it is published.
- The website loads no script from other hosts and sets a content security policy; every entrant-written string is escaped.
- Actions are pinned to commits, and Dependabot proposes updates. The server jar is downloaded from PaperMC with its checksum verified.

## Secrets

The project holds no secrets that open anything of an entrant's. The scoring job has only the default repository token. Entrants who put a token in their endpoint URL should know that the URL appears in public logs and manifests; use a dedicated, revocable one.
