Use policy complexity, not just category name, to label them easy/medium/hard.

Simple way to classify
Easy
Policies with:

1 main condition
1 action
no exceptions
no multi-step resolution
no escalation logic
Examples:

approve_refund if within window and unused
deny_replacement if outside window
simple request_clarification
Medium
Policies with:

2–3 conditions
a few exceptions
one or two edge cases
maybe one escalation rule
limited branching
Examples:

refund policy with damaged/wrong-item exceptions
replacement policy with a few valid reasons
payment policy with duplicate charge + failed payment + bank delay
Hard
Policies with:

many branches
multiple exceptions that override normal rules
multi-step flows like offer_resolution_options
escalation/fraud/conflicting info handling
overlapping rules or priority resolution needed
Examples:

payment policy with suspicious activity and bank delay
refund policy with multiple override cases
any policy where the model must decide between refund, replacement, escalate, or clarify
For your three policies
Refund → Medium
Replacement → Medium
Payment → Medium to Hard
If suspicious activity and escalation are included, I’d mark it Hard .
Practical rule of thumb
If a human can decide it with:

one if-statement → Easy
a few if/else branches → Medium
nested conditions + exceptions + escalation → Hard
Best approach for labeling
For each policy, ask:

How many valid outcomes are there?
Do exceptions override normal rules?
Is clarification needed?
Is escalation possible?
Do I need to compare multiple fields together?
If the answer is mostly no → Easy
If some are yes → Medium
If many are yes → Hard

If you want, I can also turn your