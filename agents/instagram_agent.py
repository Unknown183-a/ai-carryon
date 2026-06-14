# agents/instagram_agent.py
import os
import time
from dotenv import load_dotenv

load_dotenv()

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

def post_reel(video_path, caption):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    abs_path = os.path.abspath(video_path)
    
    options = webdriver.ChromeOptions()
    options.add_argument("--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)")
    # Remove headless so you can see what's happening
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get("https://www.instagram.com/accounts/login/")
        time.sleep(3)
        
        driver.find_element(By.NAME, "username").send_keys(INSTAGRAM_USERNAME)
        driver.find_element(By.NAME, "password").send_keys(INSTAGRAM_PASSWORD)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(5)
        
        print("✅ Logged in! Browser will stay open — check it.")
        input("Press Enter after you see the Instagram home feed...")
        
        print("✅ Session ready — full automation coming next!")
    finally:
        driver.quit()

if __name__ == "__main__":
    post_reel("output/final_video.mp4", "Test #ai #tech")
