# Overview

This page explains Manthan in plain words. It has no code.

## The problem

Companies now put AI models inside chat apps, search tools and agents that can act on their own.
These models read text from many places: the user, documents, emails and tool descriptions.
Some of that text can come from an attacker. The model cannot always tell data from orders.

Security teams already know this kind of problem from older systems. So each idea below starts with
its classic security twin.

## Red teaming is a penetration test for AI

In a penetration test, a team attacks its own network to find weak points before a real attacker does.
Manthan does the same for an AI model. It attacks a model that runs on my own laptop, and it counts
how often the attacks work.

## Three ways in

**Prompt attacks are like SQL injection.** In SQL injection, text typed into a form is run as a
database order. In a prompt attack, a message makes the model follow the attacker instead of its
own rules. In Manthan, the target model holds a fake secret code and is told never to share it.
A second model plays the attacker and tries to get the code out, one message at a time.

**Poisoned files are like a supply-chain attack.** In a supply-chain attack, one bad part goes into
a product and the product then does harm. Many AI apps first search a set of documents, then answer
from what they find. Manthan adds poisoned documents to that set and checks if the answer changes.
The poison only changes facts about a made-up place, not anything harmful.

**Hidden orders in an email are like phishing.** In phishing, an email tricks a person into giving
away a password. An AI agent can read emails and use tools, so a hidden order in an email can trick
it too. Manthan's agent reads an inbox and tool descriptions that contain hidden orders to send a
fake key to a fake attacker.

## Judges are like an intrusion detector

Someone has to decide if each attack worked. Manthan uses judge models for this. A judge is like an
intrusion detector: it can miss real attacks, and it can raise false alarms. So I tested the judge
on replies with known answers before I trusted its numbers. Its false-alarm rate was 19%, and my
goal was 15%. That goal is not met yet, and the results page says so.

## Why it runs on a laptop

Every model runs locally. There is no cloud account, no paid API and no GPU. After a one-time model
download, the whole test runs offline. Anyone with a normal laptop can repeat it.

## What it found

- Some prompt attacks worked: 20 of 60 attempts made the target leak its secret code.
- A guard model in front of the target stopped 18 of the 20 attacks that worked without it.
  Not all of them.
- A few poisoned files were enough to change most answers. Four defence layers together stopped it
  in these tests, but two of those layers had help that real systems do not get.
- No agent attack worked in these runs. That does not mean the agent is safe.

More detail is in [results.md](results.md). The safety rules are in [SECURITY.md](../SECURITY.md).
