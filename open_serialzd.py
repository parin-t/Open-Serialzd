from playwright.sync_api import sync_playwright
import pandas as pd
import time
import os
import math

EXCEL_FILE = "reviews.xlsx"
SHOW_NAME = input('Please enter thw show you would like to review >>')   # exact show name on Serializd

# ------------------ Helpers (UI actions) ------------------ #
def set_date(page, date_str):
    """Set the date in the date picker (expects MM/DD/YYYY)."""
    container = page.wait_for_selector("div.react-datepicker__input-container", timeout=8000)
    date_input = container.query_selector("input")
    if not date_input:
        raise RuntimeError("Date input not found")
    date_input.click()
    time.sleep(0.15)
    date_input.press("Control+A")
    time.sleep(0.05)
    date_input.press("Backspace")
    time.sleep(0.05)
    date_input.type(date_str, delay=50)
    date_input.press("Enter")
    time.sleep(0.2)

def select_rating(page, rating, retries=3):
    """Click visual star rating by moving mouse to correct position.
       rating: 0..10 (integers allowed), 0 means no star click."""
    if rating is None or rating <= 0 or (isinstance(rating, float) and math.isclose(rating, 0.0)):
        return True
    # normalize to int 0..10
    try:
        r = (rating)
    except Exception:
        r = 0
    if r <= 0:
        return True

    for attempt in range(retries):
        try:
            stars = page.wait_for_selector("div.review-input-rating-stars", timeout=8000)
            page.evaluate("(el) => el.scrollIntoView({behavior: 'smooth', block: 'center'})", stars)
            time.sleep(0.25)
            box = stars.bounding_box()
            if not box:
                raise RuntimeError("Couldn't get bounding box for rating stars")
            pct = r / 11
            margin = 0.03
            pct = max(margin, min(1 - margin, pct))
            x = box["x"] + pct * box["width"]
            y = box["y"] + box["height"] / 2
            page.mouse.move(x, y, steps=11)
            time.sleep(0.08)
            page.mouse.click(x, y)
            time.sleep(0.3)
            # optional verification via status element
            status_el = page.query_selector("div.review-input-rating-stars p[role='status']")
            if status_el:
                txt = status_el.inner_text().strip()
                if any(ch.isdigit() for ch in txt):
                    return True
            else:
                return True
        except Exception as e:
            print(f"[select_rating] attempt {attempt+1} error: {e}")
            time.sleep(0.4)
    print("[select_rating] failed after retries")
    return False

def click_favorite(page):
    """Click the favorite (heart) button if present."""
    # try svg first, then parent div
    if page.query_selector("div.common-hover-link svg[data-icon='heart']"):
        page.locator("div.common-hover-link svg[data-icon='heart']").click()
        time.sleep(0.25)
        return True
    if page.query_selector("div.common-hover-link"):
        page.locator("div.common-hover-link").first.click()
        time.sleep(0.25)
        return True
    print("Favorite button not found.")
    return False

def reopen_quick_log_and_select_show(page):
    """After a submit the UI may return home; reopen Quick Log and re-select the show."""
    page.click("button:has-text('Quick Log')")
    page.wait_for_selector("input[placeholder='What are you looking for?']", timeout=10000)
    time.sleep(0.25)
    page.get_by_placeholder("What are you looking for?").fill(SHOW_NAME)
    time.sleep(0.6)
    # there may be multiple posters matching the alt text; pick the first one
    page.locator(f"img[alt='Poster for {SHOW_NAME}']").first.click()
    time.sleep(1.0)

# ------------------ High-level single-row processor ------------------ #
def process_row(page, row):
    """
    row is a dict-like (season, episode, date, rating, favorite, review)
    Returns True on success, False on failure for this row.
    """
    season = int(row.get("Season"))
    episode = row.get("Episode")
    rating = row.get("Rating")
    favorite = bool(row.get("Favorite?")) if not pd.isna(row.get("Favorite?")) else 0
    review_text = str(row.get("Review", "") or "")
    # Normalize date to MM/DD/YYYY
    raw_date = row.get("Date")
    if pd.isna(raw_date) or raw_date == "":
        print("Missing date for row, skipping.")
        return False
    try:
        dt = pd.to_datetime(raw_date)
        date_str = dt.strftime("%m/%d/%Y")
    except Exception:
        # if parsing fails, use the raw string (hope it's consistent)
        date_str = str(raw_date)

    print(f"Logging Season {season} Episode {episode if not pd.isna(episode) else 'SEASON'}  Date={date_str} Rating={rating} Favorite={favorite}")

    # Select season
    season_select = page.locator("select.common-dropdown").nth(0)
    season_select.wait_for(timeout=8000)
    # Use value or label? we use label "Season X"
    try:
        season_select.select_option(label=f"Season {season}")
    except Exception:
        # fallback: try selecting by value if label fails
        opts = season_select.evaluate("el => Array.from(el.options).map(o=>({v:o.value, t:o.text}))")
        # try to find option whose text includes the season number
        picked = None
        for o in opts:
            if f"Season {season}" in o["t"]:
                picked = o["v"]; break
        if picked:
            season_select.select_option(value=picked)
        else:
            print(f"Couldn't select Season {season} - options: {opts}")
            return False
    time.sleep(0.4)

    # If episode is provided (not NaN), select it
    if not pd.isna(episode) and str(episode).strip() != "":
        episode_select = page.locator("select.common-dropdown").nth(1)
        episode_select.wait_for(timeout=8000)
        # Episode in the sheet might be int; we convert to string value matching option value
        ep_val = str(int(episode)) if (not pd.isna(episode) and float(episode).is_integer()) else str(episode)
        try:
            episode_select.select_option(value=ep_val)
        except Exception:
            # fallback: try select by label that starts with ep number
            opts = episode_select.evaluate("el => Array.from(el.options).map(o=>({v:o.value, t:o.text}))")
            picked = None
            for o in opts:
                if o["t"].strip().startswith(str(int(float(episode)))):
                    picked = o["v"]; break
            if picked:
                episode_select.select_option(value=picked)
            else:
                print(f"Couldn't select Episode {episode} (options: {opts})")
                return False
        time.sleep(0.4)
    else:
        # season-level review => do not touch episode selector
        time.sleep(0.15)

    # Set date
    try:
        set_date(page, date_str)
    except Exception as e:
        print("Date set failed:", e)
        return False

    # Set rating
    try:
        if not select_rating(page, rating):
            print("Rating warning: failed to set rating reliably")
    except Exception as e:
        print("Rating set exception:", e)

    # Click favorite if asked
    if favorite:
        try:
            click_favorite(page)
        except Exception as e:
            print("Favorite click failed:", e)

    # Fill review text (if any)
    try:
        review_box = page.wait_for_selector("textarea.review-input-text-area", timeout=8000)
        review_box.fill(review_text)
        time.sleep(0.25)
    except Exception as e:
        print("Review text fill failed:", e)
        # some rows might be OK without review text; continue

    # Submit
    try:
        submit_btn = page.wait_for_selector("button:has-text('Submit log')", timeout=8000)
        submit_btn.click()
        time.sleep(1.0)  # let server register
    except Exception as e:
        print("Submit failed:", e)
        return False

    return True

# ------------------ Main runner: read Excel, login, loop ------------------ #
def main():
    # read excel
    if not os.path.exists(EXCEL_FILE):
        print(f"{EXCEL_FILE} not found in working directory.")
        return

    df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
    # Normalize column names (strip)
    df.columns = [c.strip() for c in df.columns]

    # Required columns check
    expected = {"Season", "Episode", "Date", "Rating", "Favorite?", "Review"}
    if not expected.issubset(set(df.columns)):
        print("Excel missing required columns. Expected:", expected)
        print("Found:", set(df.columns))
        return

    # Convert rows to list of dicts for simple iteration
    rows = df.to_dict(orient="records")

    # Credentials from env
    email = os.getenv("SER_EMAIL")
    password = os.getenv("SER_PASS")
    if not email or not password:
        print("Set SER_EMAIL and SER_PASS environment variables before running.")
        return

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            page.goto("https://www.serializd.com")
            # Login
            page.click("text=Log In")
            time.sleep(0.5)
            page.fill("input[type='email']", email)
            page.fill("input[type='password']", password)
            page.click("button:has-text('Sign in')")
            time.sleep(1.0)

            # Quick Log + search the show once
            page.click("button:has-text('Quick Log')")
            page.wait_for_selector("input[placeholder='What are you looking for?']", timeout=10000)
            page.get_by_placeholder("What are you looking for?").fill(SHOW_NAME)
            time.sleep(0.6)
            page.locator(f"img[alt='Poster for {SHOW_NAME}']").first.click()
            time.sleep(1.0)

            # Loop through rows
            total = len(rows)
            for idx, row in enumerate(rows, start=1):
                print(f"\n=== Processing row {idx}/{total} ===")
                try:
                    ok = process_row(page, row)
                    if not ok:
                        print(f"Row {idx} reported failure. Continuing to next row.")
                    else:
                        print(f"Row {idx} done.")
                except Exception as e:
                    print(f"Unhandled exception on row {idx}: {e}")
                    # keep going

                # If not the last row, reopen Quick Log and re-select the show
                if idx < total:
                    try:
                        reopen_quick_log_and_select_show(page)
                    except Exception as e:
                        print("Failed to reopen quick log for next row:", e)
                # small human-like pause between rows
                time.sleep(1.0)

            print("All rows processed. Closing browser in 5s.")
            time.sleep(5)
        finally:
            browser.close()

if __name__ == "__main__":
    main()
