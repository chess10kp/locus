Login managers
An introduction
March 12, 2022, on Kenny Levinsen's blog, 2374 words

Have you ever wondered what a login manager does, what a display manager or PAM is, or why you need any of that? If so, then this post which will walk through the functions of a login manager with (pseudo-)examples1 in C may be for you.
What is a login manager

The high-level task of a login manager is quite simple:

    It asks you a series of questions to determine what user to log you in as.
    It does whatever setup is needed to run something as your user.
    It starts a shell for your user with appropriate privileges.

Nothing more2, nothing less. On a basic UNIX system where you log in through the kernel console, login(1) takes the role of your login manager. The component that asks questions is in some cases separated from the main login manager to make it replaceable, in which case it is usually referred to as a greeter, as is the case in greetd and lightdm.

Without a login manager, everything either runs as root or as a pre-determined user. A pre-determined user is fine for daemons, and for certain devices where a user is not expected to authenticate - smart TVs, infotainment systems, etc. - it is even good enough for the final interactive shell. This is trivial to implement, as can be seen here where we change user to “http” on a POSIX platform before running an executable (taken and simplified from autologin):

// Proper error handling omitted for brevity. Reading the documentation and
// adding appropriate error handling is left as an exercise for the reader.
struct passwd *pwd = getpwnam("httpd");
initgroups(pwd->pw_name, pwd->pw_gid);
setgid(pwd->pw_gid);
setuid(pw->pw_uid);

// We are now running as "httpd", so do something
execl("/bin/httpd", "httpd", NULL);

This is called “dropping privileges”, as you go from a highly privileged state (root) to a less privileged state (a regular user). Only root is allowed to do this through setgid/setuid (or on Linux, those with CAP_SETUID).

While the above successfully changes user to whatever you may wish, it does not authenticate the user as there is no login. For that we need to add a few more moving parts.
A simple login manager

To become a simple login manager, we need to ask for a username and password and validate the input against a database of properly hashed passwords3.

In modern Linux distributions4, your hashed password is stored in /etc/shadow5, readable only to root. Manually parsing /etc/shadow and validating hashed passwords is outside the scope of this post (spoiler alert: we avoid doing that later)6. For now, pretend that int check_password(struct passwd *) takes care of that.

// Proper error handling omitted for brevity. Reading the documentation and
// adding appropriate error handling is left as an exercise for the reader.
char *username = NULL, *password = NULL;
size_t len = 0;
ssize_t read = 0;

printf("Username: ");
read = getline(&username, &len, stdin);
if (read < 1) {
	fprintf(stderr, "Please type a username\n");
	exit(EXIT_FAILURE);
}
username[read-1] = '\0';

printf("Password: ");
read = getline(&password, &len, stdin);
if (read < 1) {
	fprintf(stderr, "Please type a password\n");
	exit(EXIT_FAILURE);
}
password[read-1] = '\0';

struct passwd *pwd = getpwnam(username);
if (check_password(pwd) == -1) {
	fprintf(stderr, "Impostor!\n");
	exit(EXIT_FAILURE);
}

// Let us change to who they claim they are...
initgroups(pwd->pw_name, pwd->pw_gid);
setgid(pwd->pw_gid);
setuid(pwd->pw_uid);

// Change directory to the user home and exec their shell
chdir(pwd->pw_dir);

// Set a few expected environment variables
setenv("USER", pwd->pw_name, 1);
setenv("LOGNAME", pwd->name, 1);
setenv("HOME", pwd->pw_dir, 1);
setenv("SHELL", pwd->pw_shell, 1);

// We use '-' as argv[0] to the process to signal that it is interactive
execlp(pwd->pw_shell, '-', NULL);

Apart from lacking error handling (which is crucial in a login manager!) and lacking implementation of check_password, this would work as a basic login manager for local accounts.

This will unfortunately not be sufficient for remotely authenticated users (e.g. LDAP), not to mention alternative means of authentication (e.g. TOTP or hardware tokens). If we wish to support that and maintain our sanity, we are going to need some external assistance.
Pluggable Authentication Modules

Implementing every possible combination of authentication rules and mechanisms a system may need inside every tool that may need it would not be a good use of time. Instead, we have been given (or been cursed with, depending on perspective) PAM: A modular library that takes care of these functions for us.

Use of PAM is fairly straight forward:

    Implement “struct pam_conv” to give PAM a way to hold a conversation with the user.
    Open a PAM handle with pam_start(3), specifying what service is asking and providing your struct pam_conv implementation.
    Ask PAM to do the login-related task you need, such as pam_authenticate(3) to authenticate the user. PAM will chat with the user as it sees fit by calling your struct pam_conv implementation.

The PAM conversation

Instead of having a fixed credential format such as a username and password, PAM defines a conversation. Whenever a PAM method is called, the underlying modules are given the freedom to ask the user any question (secret or not), or present any statement (error or not) that they see fit as part of their operation.

As we are used to associating credentials with username/password pairs, this conversation can seem a little complicated and unintuitive, and it disallows the common UI pattern of putting the username and password prompt together. On the other hand, by removing assumptions it brings a lot of flexibility.

While pam_unix.so asks the familiar “Password: " question, pam_oath.so will ask a “One-type password (OATH): " question and wait for you to enter a one-time password, while pam_motd.so will prompt the user with the message of the day as an info message. A pam_no_pineaples.so may ask you about your opinion on pineapple pizza to determine if you are worthy of login.

By implementing an unassuming conversation function, the login manager does not need to know anything about the underlying implementation of these modules. It merely forwards messages and their responses.
The PAM stack and its modules

PAM does not provide any functionality on its own, and instead relies on modules to do all the heavy lifting. Many of these modules are supplied by the PAM project itself, but any shared library implementing the needed functions can be a module.

Whenever a login manager starts a PAM session, it must specify its service name. PAM looks for this service name in /etc/pam.d (see pam.conf(5)) and loads the configuration file found there. login(1) specifies “login” as its service name, and thus loads /etc/pam.d/login. Each line in this configuration file contains a type, a control flag, the name of the module and any arguments passed to it. Distribution-provided PAM stacks are usually littered with includes of other stacks, so let us instead look at a simple and flat example PAM stack:

# Example stack, do not use directly.
# Read pam.conf(5) for more information about the syntax

auth		required	pam_securetty.so
auth		requisite	pam_nologin.so
auth		required	pam_shells.so
auth		required	pam_unix.so
account		required	pam_unix.so
password	required	pam_unix.so
session		optional	pam_loginuid.so
session		optional	pam_keyinit.so
session		required	pam_limits.so
session		required	pam_unix.so

pam_start(3) uses this to load all the modules that a service would like to use, and uses them sequentially for the purposes requested. Using the above we can see that the authentication process7 becomes:

    pam_securetty.so is asked to authenticate the user. This module will fail if authenticating as root from a tty it does not deem “secure”, and will succeed otherwise.
    pam_nologin.so is asked to authenticate the user. This module will fail if /etc/nologin or /var/run/nologin exists, and will succeed otherwise. If this module fails, the authentication process stops immediately due to being “requisite”.
    pam_shells.so is asked to authenticate the user. This module will succeed if the users shell is in the /etc/shells list, and will fail otherwise.
    pam_unix.so is asked to authenticate the user. This module will ask the user for their password. It will succeed if it matches and fail otherwise.

It performs a few checks and asks us for a password. Fairly simple.
Using PAM to authenticate

We started looking at PAM in order to provide an implementation of check_password in our sample login manager, so let us see how that would look with PAM:

// Proper error handling omitted for brevity. Reading the documentation and
// adding appropriate error handling is left as an exercise for the reader.

static struct pam_conv conv = {
	// misc_conv is a built-in conversation function that uses stdin/stdout
	misc_conv
	NULL,
};

pam_handle_t *pamh = NULL;
if (pam_start("my_password_checker", NULL, &conv, &pamh) != PAM_SUCCESS) {
	exit(EXIT_FAILURE);
}

// Figure out who the user claims to be
const char *username = NULL;
if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS) {
	exit(EXIT_FAILURE);
}

// See if the user can prove their claim
if (pam_authenticate(pamh, 0) != PAM_SUCCESS) {
	fprintf(stderr, "Authentication failed\n");
	exit(EXIT_FAILURE);
}
pam_end(pamh,ret);

printf("Congratulations %s, we trust you\n", username);

This should work to authenticate a user given a PAM stack at /etc/pam.d/my_password_checker, regardless what authentication this PAM stack may demand.

A proper PAM-enabled login manager should also call account and session management. For example, account management can be used to decline login on the basis of account expiry, while the session management can be used to provide auxillary services to logged in users.
A better PAM login manager

To use PAM fully, we need to add:

    Account checks, using pam_acct_mgmt
    “Credential” management, through pam_setcred
    Session management, through pam_open_session and pam_close_session
    Environment variable handling through pam_getenvlist.

We unfortunately need to call pam_close_session after the user shell has exited, so we also have to add a fork.

// Proper error handling omitted for brevity. Reading the documentation and
// adding appropriate error handling is left as an exercise for the reader.

static struct pam_conv conv = {
	misc_conv, // uses stdin/stdout for messages
	NULL,
};

pam_handle_t *pamh = NULL;
const char *username = NULL;
int ret;

if (pam_start("my_login_manager", NULL, &conv, &pamh) != PAM_SUCCESS) {
	exit(EXIT_FAILURE);
}
if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS) {
	fprintf(stderr, "Could not get username\n");
	exit(EXIT_FAILURE);
}
if (pam_authenticate(pamh, 0) != PAM_SUCCESS) {
	fprintf(stderr, "Authentication failed\n");
	exit(EXIT_FAILURE);
}
if (pam_acct_mgmt(pamh, 0) != PAM_SUCCESS) {
	fprintf(stderr, "Account is not valid\n");
	exit(EXIT_FAILURE);
}
if (pam_setcred(pamh, PAM_ESTABLISH_CRED) != PAM_SUCCESS) {
	fprintf(stderr, "Could not establish account credentials\n");
	exit(EXIT_FAILURE);
}
if (pam_open_session(pamh, 0) != PAM_SUCCESS) {
	fprintf(stderr, "Could not open a session\n");
	exit(EXIT_FAILURE);
}

pid_t child = fork();
if (child == 0) {
	struct passwd *pwd = getpwnam(username);

	// Let us change to who they claim they are...
	initgroups(pwd->pw_name, pwd->pw_gid);
	setgid(pwd->pw_gid);
	setuid(pwd->pw_uid);

	// Change directory to the user home and exec their shell
	chdir(pwd->pw_dir);

	// Set environment variables from PAM modules
	char **env = pam_getenvlist(pamh);
	for (int idx = 0; env && env[idx]; idx++) {
		putenv(env[idx]);
	}

	// Set a few expected environment variables
	setenv("USER", pwd->pw_name, 1);
	setenv("LOGNAME", pwd->name, 1);
	setenv("HOME", pwd->pw_dir, 1);
	setenv("SHELL", pwd->pw_shell, 1);

	// We use '-' as argv[0] to the process to signal that it is interactive
	execlp(pwd->pw_shell, '-', NULL);
}

int res;
while ((res = waitpid(child, NULL, 0)) <= 0) {
	if (res == -1 && errno != EINTR) {
		fprintf(stderr, "waitpid failed: %s (%d)\n", strerror(errno), errno);
		break;
	}
}

pam_close_session(pamh, 0);
pam_setcred(pamh, PAM_DELETE_CRED);
pam_end(pamh, PAM_SUCCESS);

And there we have it! We have arrived at what a normal login manager like login(1) is doing under the hood.
What is a display manager

A display manager is an old term used to refer to login managers designed with X sessions in mind. These login managers present a graphical login prompt (a greeter) and starts a a graphical shell for the user (disregarding the shell entry of the users struct passwd entry). These login managers could be considered to control access to the X display server, hence the name.

Nowadays display servers are run as the end-user itself. In this setup, the display manager runs its own display server to present its greeter, and then either starts the end-user session on another VT, or tears down its own display server to make room for the end-user (GDM does the former while greetd does the latter).

The terms are used interchangeably when referring to graphical login managers, but I consider “login manager” to be a more meaningful term, as it includes the primary function in the name.
Conclusion

As we can see, a login manager is a quite simple application, and PAM is not particularly complicated to work with. What you do with this knowledge is up to you.

If you are merely interested in login managers for the purpose of making alternative greeter UIs, take a look at greetd which takes care of all the mechanics for you. If you are interested in writing modules or applications for PAM, or in figuring out how to properly administrate it, take a look at the guides in the PAM documentation. These can usually be found as part of the pam package in /usr/share/doc, but can also be found as a docs tarball on the PAM release page.

    A login manager is a highly security-sensitive application, and extreme care should be taken when writing one. The examples herein are only of educational value to show the relevant concepts, and should not be considered production-quality code. Use existing login managers where possible. ↩︎

    Despite somewhat misleading statements in their manpages, systemd-logind(8) and elogind(8) are not in fact login managers as per the definition used in this post. Instead, these daemons provide several auxillary services to logged in users after the login manager has done its job. An important one is seat management, which is a topic for another post. ↩︎

    Passwords must always be stored using a proper password-hashing function, such as sha512crypt or argon2 with an appropriate cost parameter. Always research the state of such primitives before use and select the current industry standard. ↩︎

    Other UNIX-like operating systems have similar structures. Refer to their respective documentation to find their location and format. ↩︎

    Passwords used to be stored in /etc/passwd, but being world-readable turned out to be an issue as cracking password hashes became a feasible attack. As /etc/passwd must be world readable to perform user lookups, the password were moved to the root-only /etc/shadow file as part of the Shadow Suite. ↩︎

    Further information about password validation can be found in passwd(5), shadow(5) and crypt(3). For a practical example, look at pam_sm_authenticate in pam_unix. ↩︎

    The “password” PAM type is for changing password, not for authentication. ↩︎

© 2025, Kenny Levinsen | Sourcehut | GitHub | Levinsen Software | Donate
