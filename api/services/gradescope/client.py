# https://pypi.org/project/fullGSapi/
from fullGSapi.api.client import GradescopeClient as GradescopeBaseClient
import threading

class GradescopeClient(GradescopeBaseClient):
    def __init__(self, timeout: int = 1800):
        """
        Initializes the extended fullGSapi Gradescope client with an inactivity timer.

        Parameters:
            timeout (int): Timeout in seconds for inactivity logout. Default is 1800 seconds (30 minutes).
        """
        super().__init__()  # Initialize the parent class (GradescopeBaseClient)
        self.timeout = timeout
        self.inactivity_timer = None
        self.lock = threading.Lock() # This is used for login synchronization

    def reset_inactivity_timer(self):
        """
        Resets or starts the inactivity timer for logging out the Gradescope client.

        Cancels any existing timer and starts a new one. When the timer expires, 
        it calls the `logout` method from this class to log out the client.

        Logout automatically if there are X minutes of inactivity for security reasons.
        """
        if self.inactivity_timer is not None:
            self.inactivity_timer.cancel()
        self.inactivity_timer = threading.Timer(self.timeout, self.logout)
        self.inactivity_timer.start()
    
    def set_timer(self, newTimeout: int):
        """
        Set the timeout to the new timeout.
        """
        self.timeout = newTimeout
    
    def log_in(self, email: str, password: str) -> bool:
        """
        Logs into Gradescope. This overriden method is thread-safe.
        """
        if not self.logged_in or not self.verify_logged_in():
            with self.lock:  # Ensures only one thread can execute this block at a time
                if self.logged_in:  # Double-check inside the lock to avoid redundant login attempts
                    self.reset_inactivity_timer()
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
                    self.reset_inactivity_timer()
                    return True
                return False
        # We are already logged in, so reset the inactivity timer
        self.reset_inactivity_timer()

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
