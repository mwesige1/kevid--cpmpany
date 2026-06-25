import socket
import hashlib
import binascii
from django.conf import settings


class MikrotikAPI:
    """
    Handles communication with the Mikrotik router
    using the Mikrotik API protocol on port 8728.
    Supports both RouterOS 6.x (MD5) and 7.x (plain).
    """

    def __init__(self, router=None):
        if router:
            # Use credentials from the router object
            self.host     = router.connection_address
            self.username = router.api_username
            self.password = router.api_password
            self.port     = router.api_port
        else:
            # Fall back to settings for backwards compatibility
            self.host     = settings.ROUTER_IP
            self.username = settings.ROUTER_USER
            self.password = settings.ROUTER_PASSWORD
            self.port     = 8728
        self.sock = None

    def connect(self):
        """
        Opens a TCP socket connection to the Mikrotik router.
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"Mikrotik connection error: {e}")
            return False

    def disconnect(self):
        """
        Closes the socket connection to the router.
        """
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def send_sentence(self, sentence):
        """
        Sends a command to the Mikrotik router.
        Mikrotik API uses a special encoding format
        where each word is prefixed with its length.
        """
        for word in sentence:
            encoded = word.encode('utf-8')
            length  = len(encoded)

            if length < 0x80:
                self.sock.send(bytes([length]))
            elif length < 0x4000:
                length |= 0x8000
                self.sock.send(bytes([
                    (length >> 8) & 0xFF,
                     length       & 0xFF
                ]))
            else:
                length |= 0xC0000000
                self.sock.send(bytes([
                    (length >> 24) & 0xFF,
                    (length >> 16) & 0xFF,
                    (length >> 8)  & 0xFF,
                     length        & 0xFF
                ]))

            self.sock.send(encoded)

        # Send empty word to mark end of sentence
        self.sock.send(bytes([0]))

    def read_sentence(self):
        """
        Reads a response sentence from the Mikrotik router.
        """
        sentence = []
        while True:
            word = self.read_word()
            if word is None:
                break
            sentence.append(word)
        return sentence

    def read_word(self):
        """
        Reads a single word from the router response.
        """
        length = self.read_length()
        if length == 0:
            return None
        word = b''
        while len(word) < length:
            chunk = self.sock.recv(length - len(word))
            if not chunk:
                break
            word += chunk
        return word.decode('utf-8')

    def read_length(self):
        """
        Reads the length prefix of a word in
        Mikrotik's binary protocol format.
        """
        byte = self.sock.recv(1)
        if not byte:
            return 0
        b = byte[0]
        if b & 0x80 == 0:
            return b
        elif b & 0xC0 == 0x80:
            return ((b & 0x3F) << 8) | self.sock.recv(1)[0]
        elif b & 0xE0 == 0xC0:
            b2 = self.sock.recv(2)
            return ((b & 0x1F) << 16) | (b2[0] << 8) | b2[1]
        else:
            b2 = self.sock.recv(3)
            return ((b & 0x0F) << 24) | (b2[0] << 16) | (b2[1] << 8) | b2[2]

    def login(self):
        """
        Authenticates with the Mikrotik router.
        RouterOS 7.x — sends username and password directly.
        RouterOS 6.x — uses MD5 challenge-response.
        Auto-detects which method to use.
        """
        try:
            # ── Try RouterOS 7.x login first ──────────
            # Send username and password directly
            self.send_sentence([
                '/login',
                f'=name={self.username}',
                f'=password={self.password}'
            ])

            response = self.read_sentence()
            print(f"Login response: {response}")

            # RouterOS 7.x returns !done immediately on success
            if any(word == '!done' for word in response):
                return True

            # RouterOS 6.x returns a challenge in =ret=
            challenge = None
            for word in response:
                if word.startswith('=ret='):
                    challenge = word[5:]
                    break

            if challenge:
                # ── RouterOS 6.x MD5 fallback ──────────
                md5 = hashlib.md5()
                md5.update(b'\x00')
                md5.update(self.password.encode('utf-8'))
                md5.update(binascii.unhexlify(challenge))
                hashed = md5.hexdigest()

                self.send_sentence([
                    '/login',
                    f'=name={self.username}',
                    f'=response=00{hashed}'
                ])

                response = self.read_sentence()
                print(f"MD5 Login response: {response}")
                return any(word == '!done' for word in response)

            # Check for errors
            for word in response:
                if word.startswith('!trap'):
                    print(f"Login failed: {response}")
                    return False

            return False

        except Exception as e:
            print(f"Login error: {e}")
            return False

    def run_command(self, command):
        """
        Connects, logs in, runs a command and disconnects.
        This is the main method we call from our views.
        """
        try:
            if not self.connect():
                return False
            if not self.login():
                return False
            self.send_sentence(command)
            response = self.read_sentence()
            print(f"Command response: {response}")
            return True
        except Exception as e:
            print(f"Mikrotik command error: {e}")
            return False
        finally:
            self.disconnect()

    def run_command_with_response(self, command):
        """
        Connects, logs in, runs a command and returns
        the full response. Used when we need to read
        data back from the router e.g. finding binding IDs.
        """
        try:
            if not self.connect():
                return []
            if not self.login():
                return []
            self.send_sentence(command)
            response = self.read_sentence()
            return response
        except Exception as e:
            print(f"Mikrotik command error: {e}")
            return []
        finally:
            self.disconnect()


def grant_internet_access(mac_address, ip_address, router=None):
    """
    Creates a command in the queue for the router to grant internet.
    Router polls Django and executes the command locally.
    Falls back to direct API if router is directly reachable.
    """
    try:
        # ── Try direct API first ───────────────────────
        if router and is_router_reachable(router.connection_address):
            api      = MikrotikAPI(router=router)
            response = api.run_command_with_response([
                '/ip/hotspot/ip-binding/print',
                f'?mac-address={mac_address}',
            ])

            binding_id   = None
            binding_type = None
            for word in response:
                if word.startswith('=.id='):
                    binding_id = word[5:]
                if word.startswith('=type='):
                    binding_type = word[6:]

            if binding_id and binding_type == 'bypassed':
                print(f"✅ Already bypassed for {mac_address}")
                return True

            if binding_id and binding_type == 'blocked':
                result = api.run_command([
                    '/ip/hotspot/ip-binding/set',
                    f'=.id={binding_id}',
                    '=type=bypassed',
                    f'=comment=WiFi_Portal_{mac_address}',
                ])
                return result

            result = api.run_command([
                '/ip/hotspot/ip-binding/add',
                f'=mac-address={mac_address}',
                '=type=bypassed',
                f'=comment=WiFi_Portal_{mac_address}',
            ])
            if result:
                print(f"✅ Direct API: granted internet to {mac_address}")
            return result

        # ── Fallback — command queue ───────────────────
        # Router is not directly reachable
        # Create a command for router to pick up on next poll
        if router:
            from network.models import RouterCommand
            RouterCommand.objects.create(
                router      = router,
                action      = 'grant',
                mac_address = mac_address,
                ip_address  = ip_address or '',
            )
            print(f"✅ Command queued: grant {mac_address} on {router.identity}")
            return True

        print(f"⚠️ No router specified for grant_internet_access")
        return False

    except Exception as e:
        print(f"grant_internet_access error: {e}")
        return False


def revoke_internet_access(mac_address, ip_address, router=None, block_type='remove'):
    """
    Creates a command in the queue for the router to revoke internet.
    Falls back to direct API if router is directly reachable.
    """
    try:
        action = 'block' if block_type == 'block' else 'revoke'

        # ── Try direct API first ───────────────────────
        if router and is_router_reachable(router.connection_address):
            api      = MikrotikAPI(router=router)
            response = api.run_command_with_response([
                '/ip/hotspot/ip-binding/print',
                f'?mac-address={mac_address}',
            ])

            binding_id   = None
            binding_type = None
            for word in response:
                if word.startswith('=.id='):
                    binding_id = word[5:]
                if word.startswith('=type='):
                    binding_type = word[6:]

            if block_type == 'block':
                if binding_id:
                    if binding_type == 'blocked':
                        return True
                    result = api.run_command([
                        '/ip/hotspot/ip-binding/set',
                        f'=.id={binding_id}',
                        '=type=blocked',
                        f'=comment=WiFi_Portal_AdminBlocked_{mac_address}',
                    ])
                else:
                    result = api.run_command([
                        '/ip/hotspot/ip-binding/add',
                        f'=mac-address={mac_address}',
                        '=type=blocked',
                        f'=comment=WiFi_Portal_AdminBlocked_{mac_address}',
                    ])
                if result:
                    print(f"✅ Direct API: blocked {mac_address}")
                return result

            else:
                if binding_id:
                    result = api.run_command([
                        '/ip/hotspot/ip-binding/remove',
                        f'=.id={binding_id}',
                    ])
                    if result:
                        print(f"✅ Direct API: revoked {mac_address}")
                    return result
                else:
                    print(f"No binding found for {mac_address}")
                    return True

        # ── Fallback — command queue ───────────────────
        if router:
            from network.models import RouterCommand
            RouterCommand.objects.create(
                router      = router,
                action      = action,
                mac_address = mac_address,
                ip_address  = ip_address or '',
            )
            print(f"✅ Command queued: {action} {mac_address} on {router.identity}")
            return True

        print(f"⚠️ No router specified for revoke_internet_access")
        return False

    except Exception as e:
        print(f"revoke_internet_access error: {e}")
        return False

def is_router_reachable(ip_address=None):
    """
    Simple check to see if the Mikrotik router
    is reachable on the network via API port 8728.
    Used by the dashboard health monitor.
    """
    try:
        host = ip_address or settings.ROUTER_IP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, 8728))
        sock.close()
        return result == 0
    except Exception:
        return False
    


def get_router_stats(ip_address=None):
    """
    Fetches real-time CPU and memory usage
    from the MikroTik router.
    Returns dict with cpu and memory percentages.
    """
    try:
        api = MikrotikAPI()
        if ip_address:
            api.host = ip_address

        if not api.connect():
            return None
        if not api.login():
            return None

        # Get CPU load
        api.send_sentence(['/system/resource/print'])
        response = api.read_sentence()
        api.disconnect()

        stats = {}
        for word in response:
            if word.startswith('=cpu-load='):
                stats['cpu'] = float(word.split('=')[2])
            if word.startswith('=free-memory='):
                free_mem = int(word.split('=')[2])
            if word.startswith('=total-memory='):
                total_mem = int(word.split('=')[2])

        if 'cpu' in stats and free_mem and total_mem:
            stats['memory'] = round(
                (1 - free_mem / total_mem) * 100, 1
            )

        return stats

    except Exception as e:
        print(f"get_router_stats error: {e}")
        return None
    


def reboot_router(router=None):
    """
    Sends a reboot command to the Mikrotik router.
    Called from the dashboard when admin clicks Reboot.
    Works through WireGuard tunnel for remote routers.
    """
    try:
        api = MikrotikAPI(router=router)
        result = api.run_command(['/system/reboot'])
        if result:
            print(f"✅ Reboot command sent to {router.identity if router else 'default router'}")
        return result
    except Exception as e:
        print(f"reboot_router error: {e}")
        return False