#!/usr/bin/env python3

from bs4 import BeautifulSoup
import requests
import re
import time
import sys

def main():
    wiki_html = open("source-table.html").read()
    currencies = parse_main_wiki_page(wiki_html)

    # If args are supplied, only use currencies which contain text of at least one of these args
    if len(sys.argv) > 1:
        def in_args(c):
            for arg in sys.argv[1:]:
                if arg in c["name"]:
                    return True
            return False
        currencies = [c for c in currencies if in_args(c)]

    for count, c in enumerate(currencies):
        slug = c["page_slug"]
        if slug == "Bitcoin":
            continue
        count_string = f"{count}/{len(currencies)}"
        smallest_denom = get_smallest_denomination(slug, c["name"], count_string)

def parse_main_wiki_page(wiki_html):
    # This code parses the table from this wiki page:
    # https://en.wikipedia.org/wiki/List_of_circulating_currencies

    soup = BeautifulSoup(wiki_html, features = "lxml")

    currency_map = {}

    rows_spanned = 0
    spanned_country = None
    for row in soup.tbody.find_all("tr"):
        children = list(row.find_all("td"))

        # Extract currency name
        if rows_spanned == 0:
            # This row's country cell isn't merged with one above, so read it
            country_tag = children[0]
            children = children[1:]
            # Extract values
            country = country_tag.a.text.strip()
            if "rowspan" in country_tag.attrs:
                rows_spanned = int(country_tag["rowspan"]) - 1
                spanned_country = country
        else:
            # This row's country cell is merged, so take the currency from above
            country = spanned_country
            rows_spanned -= 1
        assert(len(children) == 5)

        # Extract other fields
        wiki_url = children[0].a["href"].replace("/wiki/", "")
        name = children[0].a.text.strip()

        # Save currency
        if wiki_url not in currency_map:
            currency_map[wiki_url] = {
                "name": name,
                "countries": []
            }
        currency_map[wiki_url]["countries"].append(country)

    # Flatten this map back into a list
    currencies = []
    for wiki_url in currency_map:
        obj = currency_map[wiki_url]
        obj["page_slug"] = wiki_url
        currencies.append(obj)
    return currencies

def get_smallest_denomination(page_slug, name, count_string):
    print()
    print()
    print()
    print("------------------------------------")

    if page_slug in ["Russian_ruble"]:
        return

    # print()
    # print()
    # Check for cached page
    cache_path = f".wiki_cache/{page_slug}.html"
    url = "http://en.wikipedia.org/wiki/" + page_slug
    try:
        page_html = open(cache_path, "r").read()
        print(f"## {count_string} {name} :: {url} (cached)")
    except FileNotFoundError as e:
        # Cache file not found, so fetch the URL
        print(f"## {count_string} {name} :: {url} (downloading...)")
        page_html = requests.get(url).text
        with open(cache_path, "w") as f:
            f.write(page_html)
    soup = BeautifulSoup(page_html, features = "lxml")

    # ==== Get which denominations exist and how much they're worth ===
    # Maps unit names to values.  E.g. GBP would be {"£": 1, "p": 0.01}
    units = {}

    # Get the singular version from the title
    singular_name = name.split(" ")[-1]
    units[singular_name] = 1
    # Special cases for 1 and 0.01 denominations which don't appear in the wiki pages
    for one_unit in ["¥ rmb", "$", "pesos dominicano", "rls", "ll"]:
        units[one_unit] = 1
    for cent_unit in ["¢", "centavos", "cop", "st", "pt"]:
        units[cent_unit] = 0.01

    # Parse the infobox
    infobox = soup.find("table", class_="infobox")

    # Parse 'Code' out of `ISO 4271`
    iso_elem = infobox.find("th", string="ISO 4217")
    parsed_iso = parse_infobox(iso_elem, "Denominations")
    iso_code = parsed_iso["Code"].text.split("(")[0].strip()

    # Parse the `Unit` section for symbols and plurals
    unit_elem = infobox.find("th", string="Unit")
    if unit_elem is None:
        print("BRUH!  {url} has no normal unit symbol")
    else:
        parsed_unit = parse_infobox(unit_elem.parent, "Denominations")
        for key in ["Symbol", "Plural"]:
            if key not in parsed_unit:
                continue
            right_elem, _ = parsed_unit[key]
            sym_text = right_elem.text.strip()
            sym_text = sym_text.replace("\u200e", "")
            sym_text = sym_text.replace("numeric: ", "")
            sym_text = re.sub(r"\[.*?\]", "", sym_text) # Remove citations
            for sym in re.split(", | or | and |/|\(|\)", sym_text):
                sym = sym.strip()
                if sym != "" and "language" not in sym:
                    units[sym] = 1 # The name itself is worth 1

    # Parse the `denominations` section for subunits
    parsed_denoms = parse_infobox(
        soup.find("a", string="Denominations").parent.parent,
        "Demographics"
    )
    if "Subunit" in parsed_denoms:
        _, subunits = parsed_denoms["Subunit"]
        subunit_names = []
        for fraction_elem, name_elem in subunits:
            # Get subunit amount
            fraction_num, fraction_den = fraction_elem.text.split("⁄")
            amount = int(fraction_num) / int(fraction_den.replace(",", ""))
            for name in parse_subunit(name_elem):
                subunit_names.append(name)
                units[name] = amount
        # Add plurals and symbols (if they exist)
        for key in ["Plural", "Symbol"]:
            if key not in parsed_denoms:
                continue
            _, sections = parsed_denoms[key]
            for subunit_elem, other_name_elem in sections:
                subunit = parse_subunit(subunit_elem)[0]
                for other_name in parse_subunit(other_name_elem):
                    if other_name != "" and subunit in units:
                        units[other_name] = units[subunit]
    # Add normal plurals by adding 's' to everything (even if it's already a plural)
    for u in dict(units):
        units[u + "s"] = units[u]

    # Normalise deonimation values
    units = {
        unit.replace(".", "").lower() : units[unit]
        for unit in units
    }
    print(units)

    # Read the coin texts
    denoms = [] # (value, name, type, rare)
    for denom_type in ["Coin", "Banknote"]:
        key = denom_type + "s"
        if key not in parsed_denoms:
            continue # Skip in case a currency has e.g. no coins
        right_elem, elem_pairs = parsed_denoms[key]
        denoms += parse_denoms(right_elem, denom_type, False, units)
        for left_elem, right_elem in elem_pairs:
            is_rare = "Rarely" in left_elem.text
            denoms += parse_denoms(right_elem, denom_type, is_rare, units)

    # Sort denoms by increasing value
    denoms.sort(key = lambda v: v[0])

    print(denoms)
    print("Smallest:", denoms[0])


def parse_subunit(elem):
    subunit = elem.text
    subunit = re.sub("\[.*?\]", "", subunit) # Remove references
    subunit = subunit.split('"')[0] # strip after "
    subunit = subunit.strip()
    return [s.strip() for s in re.split(",|\n| or |\(|\)", subunit)]

def parse_denoms(elem, type, is_rare, units):
    # Special case for GBP, which represents their elements as a list
    if elem.ul is not None:
        text = ""
        for item in elem.find_all("li"):
            text += ", " + item.text
    else:
        text = elem.text.lower().strip()

    # Normalise text
    text = text.replace("\xa0", " ") # Replace \ns with spaces
    text = text.replace("\n", " ") # Replace \ns with spaces
    text = re.sub("bimetallic", "", text) # Remove "bimetallic"
    text = re.sub(r"\[.*\]", "", text) # Remove citations
    text = re.sub(r"\(.*\)", "", text) # Remove languages
    if text == "":
        return []
    print()
    print(text.__repr__())

    named_denoms = re.split(", | & |;|\\band\\b", text)
    # Parse 'named' unit (e.g. "1 penny") denomination backwards.  We do so backwards to more
    # easily handle cases like `1, 2, 5, 10 cents`, since we can cache the `cents` and look
    # that up in future iterations
    if not text[0].isalpha():
        named_denoms.reverse()

    denominations = []

    last_unit = None
    for name in named_denoms:
        name = name.strip()
        contains_digits = False
        for c in name:
            if c.isdigit():
                contains_digits = True
        if not contains_digits:
            continue

        # Split the denomination into numbers and everything else (i.e. the unit)
        number = ""
        unit = ""
        for c in name:
            if c.isdecimal() or c in "+⁄½":
                number += c
            elif c in ",.-": # Joining symbols, which should be ignored
                pass
            else:
                unit += c

        # Process the text
        number = parse_fraction(number)
        value_multiplier = None
        if re.match("^.*\d+/[-=]$", name):
            # Currency is like ##/- or ##/=
            value_multiplier = 1
        else:
            # Calculate unit
            unit = unit.strip()
            unit = re.sub(r"/\w*$", "", unit) # Strip words after "/" (if two names are given)
            unit = unit.strip()

            # If no unit is given, check if one was used prior (e.g. "1, 2, 5 pounds")
            if unit == "":
                unit = last_unit
                # Add the missing unit back to the denomination
                if unit.isalpha():
                    if len(unit) == 1:
                        name = name + unit # E.g. "1p"
                    else:
                        name = name + " " + unit # E.g. "1 peso"
                else:
                    name = unit + name # E.g. "$1"
            else:
                last_unit = unit

            value_multiplier = units[unit]
        value = number * value_multiplier
        denominations.append((value, name, type, is_rare))

    return denominations

def parse_fraction(text):
    if text == "½":
        return 0.5

    total = 0
    # Handle `+`
    if "+" in text:
        int_part, fraction = text.split("+")
        total += int(int_part)
    else:
        fraction = text
    # Handle fraction
    if "⁄" in fraction:
        num, den = fraction.split("⁄")
        total += int(num) / int(den)
    else:
        total += int(fraction)

    return total

# Returns a type {string: (elem, [(elem, elem)])}
def parse_infobox(heading_elem, next_section_name):
    headings = {}

    current_heading = None
    current_right_elem = None
    current_rows = []
    def add_previous_headings():
        if current_heading is None:
            return
        headings[current_heading] = (current_right_elem, current_rows)

    row = heading_elem.next_sibling
    while next_section_name not in row.text:
        left, right = row.children
        heading = left.text.strip()
        is_bold = left.find("span", class_="nobold") is None

        if is_bold:
            # Starting a new heading
            add_previous_headings()
            current_heading = heading
            current_right_elem = right
            current_rows = []
        else:
            # Continuing a previous heading
            assert(current_heading is not None)
            current_rows.append((left, right))
        row = row.next_sibling

    # Make sure to add the last heading
    add_previous_headings()

    return headings

if __name__ == "__main__":
    main()
