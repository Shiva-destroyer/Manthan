# Security policy

## Scope

Manthan is for defensive security research and learning. Its attacks run only against:

1. open-weight models that run locally on your own machine, and
2. the deliberately weak test apps that ship in this repository.

Every secret, key, credential and piece of personal data in this project is fake. No real secret is
in the repository or used at runtime. The fakes are easy to spot: `example.invalid` email addresses,
`555` phone numbers, all-zero ID numbers and keys marked `SYNTHETIC-FAKE`.

## Rules of use

- Do not run Manthan's attacks against any system you do not own or do not have written permission
  to test. Manthan has no feature to target hosted or third-party systems. Do not change it to add one.
- The agent lab runs on a Docker network marked `internal: true`, so it has no route to the internet.
  The only place the agent can send data is the `mock-exfil` listener in the lab. It logs attempts
  and stores nothing real.
- Manthan reproduces known, published attack types for measurement and defence. It has no new
  exploits and no working payloads beyond what is needed to trip a local test target.

## No paid APIs, no GPU, no network in tests

- By default, Manthan makes no paid API calls. A budget guard raises an error if a non-local backend
  is selected without the opt-in flag `budget.allow_non_local_backend`. CI never sets it.
- CI runs with network sockets turned off (`pytest-socket`), so the tests prove they need no network.
- No default code path uses CUDA or ROCm.

## Reporting a vulnerability

If you find a problem in Manthan itself, please report it privately through GitHub:
open the **Security** tab of this repository and choose **Report a vulnerability**.
You can also use the contact address in the [README](README.md). Please do not open a public issue
for a security problem.

If your own research finds a problem in a third-party product, report it to that vendor through
coordinated disclosure.

Using this tool against systems you do not own or have permission to test may be illegal. The author
accepts no liability for misuse.
