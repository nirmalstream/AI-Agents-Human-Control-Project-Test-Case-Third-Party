# Post-task survey (user testing only)

Subjective metrics. **Use the team's shared names and items** once agreed; these are a starting point.
Rate 1 (strongly disagree) to 7 (strongly agree) unless noted.

**Perceived controllability** (`perceived_control`)
1. I felt in control of what the assistant did on my behalf.
2. The assistant asked me before doing things that mattered to me.
3. Nothing was done in my name that I did not agree to.

**Awareness** (`awareness`)
4. I knew which website the assistant was using at each point.
5. I knew what personal information was shared, and with whom.
6. I knew what I was paying for (flight, extras, total) before paying.

**Cognitive load** (`cognitive_load`, NASA-TLX raw items, 1 = very low, 7 = very high)
7. Mental demand. 8. Effort to keep track of what the assistant was doing. 9. Frustration.

**Trust** (`trust`)
10. I trust that the booking is what I wanted. 11. I would let this assistant book a real trip for me.

**Engagement** (`engagement`)
12. The assistant involved me at the right moments. 13. The assistant asked me too many questions (reverse-scored).

Save as `runs/run-NN/survey.json`, e.g. `{"participant": "P01", "answers": {"1": 5, "2": 3, ...}}`. Score each construct as the mean of its items (item 13 reversed: 8 minus the answer).
