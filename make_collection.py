#!/usr/bin/env python3

import json
import re

def main():
    # Load currency data
    currencies = json.loads(open("currencies.json").read())
    # Load country data

    for c in currencies:
        print(c["name"], c["countries"])

    # Write them to a summary file in a nice format
    with open("summary.txt", "w") as f:
        f.write(make_file_contents(currencies))

def make_file_contents(currencies):
    longest_name_len = max([len(c["name"]) for c in currencies])

    s = ""
    for c in currencies:
        # Separate a run of rare denominations, which would technically have the lowest values but
        # are so hard to collect that I consider them to be optional
        rare_denoms = []
        first_common_denom = None
        for d in c["denominations"]:
            if not d["is_rare"]:
                first_common_denom = d
                break
            rare_denoms.append(d)
        # Build the string
        s += f"{c['name']} {'.' * (longest_name_len - len(c['name']))}... "
        if rare_denoms != []:
            s += f"({combined_denom_string(rare_denoms)}) "
        if first_common_denom is not None:
            s += combined_denom_string([first_common_denom])
        s += "\n"
    return s

# Given a list of denoms, creates a string like "1p, 2p, 5p" or combine common prefixes
# like "1, 5, 10 dirhams" (instead of "1 dirhams, 5 dirhams, 10 dirhams")
def combined_denom_string(denoms):
    # Split the denominations into consecutive groups which share a (prefix, suffix) pair.
    # These will then have their prefixes/suffixes merged.
    combination_groups = [] # (prefix, suffix, numbers)
    group_prefix = None
    group_suffix = None
    group_numbers = []
    def add_group():
        if group_prefix is None or group_suffix is None:
            return
        combination_groups.append((group_prefix, group_suffix, group_numbers))
    # Loop to build up the groups
    num_regex = re.compile("[0-9,⁄]+")
    for d in denoms:
        number = num_regex.findall(d["name"])[0]
        prefix, suffix = num_regex.split(d["name"])
        if prefix != group_prefix or suffix != group_suffix:
            add_group()
            group_prefix = prefix
            group_suffix = suffix
            group_numbers = []
        group_numbers.append((number, d["is_note"]))
    add_group() # Make sure to add final group

    # Join each group together independently
    string = ""
    for prefix, suffix, numbers in combination_groups:
        should_dedup_prefix = prefix.endswith(" ") and len(numbers) > 1
        should_dedup_suffix = suffix.startswith(" ") and len(numbers) > 1
        # Delimit groups with commas
        if string != "":
            string += ", "
        # Add group
        is_first_number = True
        string += prefix if should_dedup_prefix else ""
        for n, is_note in numbers:
            # Delimit with commas
            string += "" if is_first_number else ", "
            is_first_number = False
            # Add denomination
            string += "" if should_dedup_prefix else prefix
            string += n
            string += "" if should_dedup_suffix else suffix
            string += " [note]" if is_note else ""
        string += suffix if should_dedup_suffix else ""
    return string

if __name__ == "__main__":
    main()
