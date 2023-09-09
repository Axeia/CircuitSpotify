import microcontroller
import os
import adafruit_requests
import traceback

# Just used for type hinting okay to fail on-device but it helps code clarity
# for anyone reading this and IDEs out greatly.
try:
    from typing import Dict
except ImportError:
    pass
"""
Spotify for CircuitPython.

## Requirements
  * nvm support ( https://docs.circuitpython.org/en/latest/shared-bindings/nvm/index.html )
  * a session with internet connection (and thus a board that has networking capabilities)
  * CircuitPython Version 8.2.1 
    * (Do not use 8.2.2, 8.2.3 or 8.2.4, they have an incomplete certificate 
      list which will cause https connection problems)
## Initial setup steps
1. Download CircuitSpotify to your boards /lib/ directory
2. https://developer.spotify.com/ <br>
   Make and/or log in to an account 
3. https://developer.spotify.com/dashboard <br>
   Create an app
4. Copy the following data from the Basic Information dashboard page 
   of your app to your boards `settings.toml` file: 
	 ```
	CIRCUITSPOTIFY_CLIENT_ID = "Your Client ID"
	CIRCUITSPOTIFY_CLIENT_SECRET = "Your client secret"
	CIRCUITSPOTIFY_REDIRECT_URL = "Redirect URL"
	```
	*The redirect URL can be anything just make sure its URL encoded and matches 
	your Basic Information page settings. I used: https://open.spotify.com/ 
	(`CIRCUITSPOTIFY_REDIRECT_URL = "https%3A%2F%2Fopen.spotify.com%2F"`)*
5. Use your spotify account to authorize the apps required access.
Simply initializing this class after step 4 should make it print a url.
Visit this URL, grant the authorization and you'll be redirected to the
redirect_url you have set up for your app.
What is important is the code in the URL after ?code=
Copy this and paste it into settings.toml as `CIRCUITSPOTIFY_CODE`

That should be it, you have created and authorized the app on Spotify's side of things.
The code should now be able to receive a request and access token.

**NOTE**:
>With some luck you'll only have to do these steps once. However this class might
print the authorization URL once again if some kind of problem occurs in which
case you will have to repeat step 5.
"""
class CircuitSpotify():
    """
    Contains the scopes documented on:
    https://developer.spotify.com/documentation/web-api/concepts/scopes

    CircuitPython lacks an enum class but this more or less functions like one
    """
    class Scope():
        UGC_IMAGE_UPLOAD = 'ugc-image-upload'
        SCOPE_UGC_IMAGE_UPLOAD = 'user-read-playback-state'
        USER_MODIFY_PLAYBACK_STATE = 'user-modify-playback-state'
        #
        USER_READ_CURRENTLY_PLAYING = 'user-read-currently-playing'
        # Playback
        APP_REMOTE_CONTROL = 'app-remote-control'
        # streaming
        PLAYLISTS = 'Playlists'
        PLAYLIST_READ_PRIVATE = 'playlist-read-private'
        PLAYLIST_READ_COLLOBORATIVE = 'playlist-read-collaborative'
        PLAYLIST_MODIFY_PRIVATE = 'playlist-modify-private'
        PLAYLIST_MODIFY_PUBLIC = 'playlist-modify-public'
        # Follow
        USER_FOLLOW_MODIFY = 'user-follow-modify'
        USER_FOLLOW_READ = 'user-follow-read'
        # Listening History
        USER_READ_PLAYBACK_POSITION = 'user-read-playback-position'
        USER_TOP_READ = 'user-top-read'
        USER_READ_RECENTLY_PLAYED = 'user-read-recently-played'
        # Library
        USER_LIBRARY_MODIFY = 'user-library-modify'
        USER_LIBRARY_READ = 'user-library-read'
        # Users
        USER_READ_EMAIL = 'user-read-email'
        USER_READ_PRIVATE = 'user-read-private'
        # Open Access
        USER_SOA_LINK = 'user-soa-link'
        USER_SOA_UNLINK = 'user-soa-unlink'
        USER_MANAGE_ENTITLEMENTS = 'user-manage-entitlements'
        USER_MANAGED_PARTNER = 'user-manage-partner'
        USER_CREATE_PARTNER = 'user-create-partner'

    CLIENT_ID = 'CIRCUITSPOTIFY_CLIENT_ID'     # to be used for os.getenv()
    CLIENT_SECRET = 'CIRCUITSPOTIFY_CLIENT_SECRET'  # to be used for os.getenv()
    CODE = 'CIRCUITSPOTIFY_CODE'          # to be used for os.getenv()
    REDIRECT_URL = 'CIRCUITSPOTIFY_REDIRECT_URL'  # to be used for os.getenv()

    """
    session is used to access the spotify API over the web

    scopes should be an array containing the relevant scopes. 
    CircuitPythonify.Scope contains the values you can use for this

    The redirect URL shoul
    """

    def __init__(
        self,
        session: adafruit_requests.Session,
        scopes: [str],
        print_everything = False
        # auto_validate = False
        # TODO: Uncomment above parameter and if set to true will run a
        # http server listening out for a call to the redirect_url specified
        # in settings.toml. When the call is made write the received code
        # parameter to settings.toml as CIRCUITSPOTIFY_CODE
    ):
        self.print_everything = print_everything
        self._currently_playing_listeners = []
        self.session = session
        auth_base_url = 'https://accounts.spotify.com/authorize?'
        auth_url_parms = {
            'client_id':        os.getenv(self.CLIENT_ID),
            'response_type':    'code',
            # Turn scopes into a (html encoded) space seperated string
            'scope':            ' '.join(scopes)
        }

        self.auth_url = auth_base_url + self._params_to_query_string(auth_url_parms)
        
        if self.print_everything:
            print('Class variables initialized')

        # Ask user to authenticate App if there's no os.getenv(self.CODE)
        if os.getenv(self.CODE) == None:
            print(f"""
                settings.toml CIRCUITSPOTIFY_CODE not found. Please authorize this app by visiting: {self.auth_url}
                which will redirect you to a new page with url ending in "?code=long_string"
                Save this long_string in its entirety as the settings.toml CIRCUITSPOTIFY_CODE
            """)
        else:
            if self.print_everything:
                f'settings.toml code succesfully found, it is: {os.getenv(self.CODE)}'

            if self.print_everything:
                self._print_tokens()
            # self._clear_nvm()
            # self.get_and_save_tokens()
            # self._print_tokens()
            # time.sleep(5)
            # print(self.get_currently_playing())

    '''
    The dictionary that is returned is the JSON detailed over here (unless some kind of error occured):
    https://developer.spotify.com/documentation/web-api/reference/get-the-users-currently-playing-track
    '''
    def get_currently_playing(self) -> Dict:
        currently_playing_url = 'https://api.spotify.com/v1/me/player/currently-playing'

        try:
            # Send the GET request
            response = self.session.get(
                currently_playing_url, 
                headers=self.get_authorization_header()
            )
            data = response.json()

            # If the token is expired, get a new one and try again.
            if 'error' in data and data['error']['message'] == 'The access token expired':
                self._refresh_access_token()
                response = self.session.get(
                    currently_playing_url, 
                    headers=self.get_authorization_header()
                )

            data = response.json()
        except OSError as e:
            if e.args[0] == 116:
                data = { 
                    'error': {
                        'message:': ''.join(traceback.format_exception(type(e), e, e.__traceback__)),
                        'details': 'This is likely caused by not having a song playing or even paused'
                    }                       
                }
            else:
                raise

        return data
    
    def get_authorization_header(self) -> Dict:
        access_token = self._read_access_token()
        return {"Authorization": "Bearer " + access_token}


    def get_and_save_tokens(self):
        # Set the URL for the /api/token endpoint
        token_url = "https://accounts.spotify.com/api/token"

        # Set the required parameters
        params = {
            "grant_type":       "authorization_code",
            "code":             os.getenv(self.CODE),
            # "https://open.spotify.com/"
            'redirect_uri':     os.getenv(self.REDIRECT_URL),
            "client_id":        os.getenv(self.CLIENT_ID),
            "client_secret":    os.getenv(self.CLIENT_SECRET)
        }

        # Make a POST request to the /api/token endpoint
        response = self.session.post(token_url, data=params)
        # Get the JSON response
        data = response.json()

        if 'error' in data:
            if data['error'] == 'invalid_grant':
                print(
                    f'Please generate a new code and save it to settings.toml CIRCUITSPOTIFY_CODE \n{self.auth_url}')
            print(data)
            raise RuntimeError(
                "Unexpected server response: ", data["error_code"])
        else:
            self._write_tokens(data['access_token'], data['refresh_token'])

    '''
    Access to this shouldn't be needed aside from debugging during development
    '''

    def _print_tokens(self):
        access_token = self._read_access_token()
        print(f'access_token: {access_token}')
        refresh_token = self._read_refresh_token()
        print(f'refresh_token: {refresh_token}')

    '''
    CircuitPython does not seem to have a method build in to do this.
    It takes a dictionary and turns it into a 'field' 'value' pair query string

    Note that it does not do any html escaping or url encoding, it's intended
    for internal use where problematic characters are already escaped

    url_parms: Dictionary - Only a simple 2D dictionary is allowed (no nesting)
    return: str field=value&other_field=other_value
    '''

    def _params_to_query_string(self, url_parms: Dict) -> str:
        query_string = ''

        for name, value in url_parms.items():
            query_string += f'{name}={value}&'

        return query_string[:-1]  # Trims of last excess '&'

    '''
    Refreshes the access token by requesting a new one from the spotify servers
    and storing it in nvm

    See: _read_refresh_token()
    '''

    def _refresh_access_token(self):
        # Set the URL for the /api/token endpoint
        token_url = "https://accounts.spotify.com/api/token"
        refresh_token = self._read_refresh_token()

        # Set the required parameters
        params = {
            "grant_type":       "refresh_token",
            "refresh_token":    refresh_token,
            "client_id":        os.getenv(self.CLIENT_ID),
            "client_secret":    os.getenv(self.CLIENT_SECRET)
        }

        # Make a POST request to the /api/token endpoint
        response = self.session.post(token_url, data=params)

        # Get the JSON response
        data = response.json()

        # Get the new access token
        access_token = data["access_token"]
        refresh_token = self._read_refresh_token()
        if 'refresh_token' in data:
            refresh_token = data['refresh_token']
        self._write_tokens(access_token, refresh_token)

        return access_token

    """
    Writes the tokens to the non-volatile memory
    """

    def _write_tokens(self, access_token: str, refresh_token: str):
        # Merge access_token and refresh_token so they can be written in one go
        # this helps reduce the amount of write operations and preserves the memory
        tokens = access_token + refresh_token

        # Store tokens in one go
        microcontroller.nvm[0:339] = tokens.encode("utf-8")

    def _read_access_token(self) -> str:
        # Retrieve access_token (it's always 208 ASCII characters long)
        access_token = bytes(microcontroller.nvm[0:208]).decode("utf-8")
        return access_token

    def _read_refresh_token(self) -> str:
        # Retrieve refresh_token (it's always 131 ASCII characters long)
        # and starts after the 208 characters of the access_token
        offset = 208
        refresh_token = bytes(
            microcontroller.nvm[offset:offset+131]).decode("utf-8")
        return refresh_token

    """
    Used for development - you very likely do not want to use this.
    """

    def _clear_nvm(self):
        # Get the size of the nvm array
        nvm_size = len(microcontroller.nvm)
        # Write zeros to the entire nvm array
        microcontroller.nvm[0:nvm_size] = bytearray(nvm_size)
