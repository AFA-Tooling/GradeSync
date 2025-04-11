# https://pypi.org/project/fullGSapi/
from fullGSapi.api.client import GradescopeClient as GradescopeBaseClient
import threading
import requests

class GradescopeClient(GradescopeBaseClient):
    def __init__(self):
        """
        Initializes the extended fullGSapi Gradescope client with thread-safe operations for login
        and logout on a singleton instance.
        """
        super().__init__()  # Initialize the parent class (GradescopeBaseClient)
        self.lock = threading.Lock() # This is used for login synchronization

    
    def log_in(self, email: str, password: str) -> bool:
        """
        Logs into Gradescope. This overriden method is thread-safe.
        """
        if not self.logged_in or not self.verify_logged_in():
            with self.lock:  # Ensures only one thread can execute this block at a time
                if self.logged_in:  # Double-check inside the lock to avoid redundant login attempts
                    print("Logged in to Gradescope")
                    return True
                
                url = self.base_url + self.login_path
                token = self.get_token(url)
                payload = {
                    "utf8": "✓",
                    "authenticity_token": token,
                    "session[email]": email,
                    "session[password]": password,
                    "session[remember_me]": 1,
                    "commit": "Log In",
                    "session[remember_me_sso]": 0,
                }
                self.last_res = res = self.submit_form(url, url, data=payload)
                if res.ok:
                    self.logged_in = True
                    print("Logged in to Gradescope")
                    return True
                return False
        return self.logged_in


    def logout(self):
        """
        Logs out of Gradescope. This overriden method is thread-safe.
        """
        with self.lock:  # Ensures only one thread can execute this block at a time
            print("Logging out")
            if not self.logged_in:  # Double-check within the lock to avoid redundant logout attempts
                print("You must be logged in!")
                return False

            base_url = "https://www.gradescope.com"
            url = base_url + "/logout"
            ref_url = base_url + "/account"
            self.last_res = res = self.session.get(url, headers={"Referer": ref_url})
            if res.ok:
                self.logged_in = False
                return True
            return False
    