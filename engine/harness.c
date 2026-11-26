/* The test program of Linerator: get_next_line() of the student, called as a mode says.
**
**   harness [options] lines PATH      read PATH ("-": the standard input) up to NULL
**   harness [options] fd N            two calls on the fd N (never opened, or -1)
**   harness [options] closed PATH     one line, then the fd is closed, then a call
**   harness [options] multi PATH...   the files in turn (the bonus), up to NULL for all
**   harness [options] trace PATH      like lines, with each read() (for the visualizer)
**   harness [options] reopen PATH     two lines, then every read() fails up to NULL; the file
**                                     is closed, opened again (the same fd), and read again
**   harness [options] first PATH      the first line only, then the counts (no leak check:
**                                     what is left to read stays in the static)
**
** Options: --fail-malloc K (the malloc number K returns NULL; the lines are
** then read up to NULL), --fail-read K (from the read number K on, every
** read returns -1), --lang fr.
**
** It prints one event a line on its standard output:
**   L <len>       a line returned, then its bytes and a newline
**   N             NULL returned
**   F <i>         (multi) the next call reads the file number i
**   R <ret> <n>   (trace) read(fd, buf, n) returned ret, then the bytes read and a newline
**   X             the first read() made to fail was called
**   S reads=<calls> bytes=<read> first=<read before the first line> mallocs=<calls>
**   !P            the end: nothing wrong; or !L, !M, !O, !C, !X and a message
** Memory: each block is next to a protected page and becomes unreachable when
** freed (alloc.c and guard.c, from libfterator); what is still allocated at
** the end is a leak. */
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "linerator.h"
#include "lft_internal.h"

int				lft_en = 1;

ssize_t			__real_read(int fd, void *buf, size_t n);
int				lft_mf_injected(void);

static long		g_read_calls;
static long		g_read_fail_at;
static size_t	g_read_bytes;
static size_t	g_first_bytes;
static int		g_first_seen;
static int		g_trace;
static int		g_read_fail_all;

ssize_t	__wrap_read(int fd, void *buf, size_t n)
{
	ssize_t	ret;

	g_read_calls++;
	/* A broken fd stays broken: from the call K on, read() fails, NULL from there. */
	if (g_read_fail_all || (g_read_fail_at != 0 && g_read_calls >= g_read_fail_at))
	{
		if (g_read_fail_all || g_read_calls == g_read_fail_at)
			printf("X\n");
		errno = EIO;
		ret = -1;
	}
	else
		ret = __real_read(fd, buf, n);
	if (ret > 0)
		g_read_bytes += (size_t)ret;
	if (g_trace)
	{
		printf("R %zd %zu\n", ret, n);
		if (ret > 0)
			fwrite(buf, 1, (size_t)ret, stdout);
		printf("\n");
	}
	return (ret);
}

void	lft_report(char kind, const char *msg)
{
	printf("!%c %s\n", kind, msg);
	fflush(stdout);
	_exit(0);
}

void	lft_report_fmt(char kind, const char *fmt, ...)
{
	char	buf[1024];
	va_list	ap;

	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	lft_report(kind, buf);
}

/* Print what get_next_line() returned, then free it like a student would. */
static int	show(char *line)
{
	size_t	len;

	if (!g_first_seen)
	{
		g_first_seen = 1;
		g_first_bytes = g_read_bytes;
	}
	if (line == NULL)
	{
		printf("N\n");
		return (0);
	}
	len = strlen(line);
	printf("L %zu\n", len);
	fwrite(line, 1, len, stdout);
	printf("\n");
	free(line);
	return (1);
}

static void	stats(void)
{
	printf("S reads=%ld bytes=%zu first=%zu mallocs=%ld\n", g_read_calls, g_read_bytes, g_first_bytes,
		lft_malloc_calls());
}

static int	open_path(const char *path)
{
	int	fd;

	if (strcmp(path, "-") == 0)
		return (0);
	fd = open(path, O_RDONLY);
	if (fd < 0)
		lft_report(LFT_INTERNAL, TR("le fichier de test ne s'ouvre pas", "the test file cannot be opened"));
	return (fd);
}

static void	read_all(const char *path)
{
	int	fd;

	fd = open_path(path);
	while (show(get_next_line(fd)))
		;
	/* A malloc made to fail ends the lines early: the next calls go on up to
	** NULL, so that what they read again is freed at the end of the file. */
	if (lft_mf_injected())
		while (show(get_next_line(fd)))
			;
	/* Once NULL, NULL again. */
	show(get_next_line(fd));
	if (fd > 0)
		close(fd);
}

static void	read_closed(const char *path)
{
	int	fd;

	fd = open_path(path);
	show(get_next_line(fd));
	close(fd);
	show(get_next_line(fd));
}

/* From the testers of francinette (fsoares, MIT): after a failed read(), the
** static must be cleared, so that the file opened again is read from its start. */
static void	read_reopen(const char *path)
{
	int	fd;

	fd = open_path(path);
	printf("F 0\n");
	show(get_next_line(fd));
	show(get_next_line(fd));
	g_read_fail_all = 1;
	while (show(get_next_line(fd)))
		;
	g_read_fail_all = 0;
	close(fd);
	fd = open_path(path);
	printf("F 1\n");
	while (show(get_next_line(fd)))
		;
	close(fd);
}

static void	read_multi(int count, char **paths)
{
	int	fds[64];
	int	done[64];
	int	left;
	int	i;

	if (count > 64)
		count = 64;
	for (i = 0; i < count; i++)
	{
		fds[i] = open_path(paths[i]);
		done[i] = 0;
	}
	left = count;
	while (left > 0)
		for (i = 0; i < count; i++)
		{
			if (done[i])
				continue ;
			printf("F %d\n", i);
			if (!show(get_next_line(fds[i])))
			{
				done[i] = 1;
				left--;
			}
		}
	for (i = 0; i < count; i++)
		if (fds[i] > 0)
			close(fds[i]);
}

static void	usage(void)
{
	fprintf(stderr, "usage: harness [--fail-malloc K] [--fail-read K] [--lang fr] "
		"lines PATH | fd N | closed PATH | reopen PATH | multi PATH... | trace PATH | first PATH\n");
	exit(2);
}

int	main(int argc, char **argv)
{
	int	i;

	i = 1;
	while (i + 1 < argc && strncmp(argv[i], "--", 2) == 0)
	{
		if (strcmp(argv[i], "--fail-malloc") == 0)
			lft_fail_malloc_at(atol(argv[i + 1]));
		else if (strcmp(argv[i], "--fail-read") == 0)
			g_read_fail_at = atol(argv[i + 1]);
		else if (strcmp(argv[i], "--lang") == 0)
			lft_en = strcmp(argv[i + 1], "fr") != 0;
		else
			usage();
		i += 2;
	}
	if (i + 1 >= argc)
		usage();
	setvbuf(stdout, NULL, _IOFBF, 1 << 16);
	lft_install_fault_handler();
	if (strcmp(argv[i], "lines") == 0 || strcmp(argv[i], "trace") == 0)
	{
		g_trace = argv[i][0] == 't';
		read_all(argv[i + 1]);
	}
	else if (strcmp(argv[i], "fd") == 0)
	{
		show(get_next_line(atoi(argv[i + 1])));
		show(get_next_line(atoi(argv[i + 1])));
	}
	else if (strcmp(argv[i], "closed") == 0)
		read_closed(argv[i + 1]);
	else if (strcmp(argv[i], "reopen") == 0)
		read_reopen(argv[i + 1]);
	else if (strcmp(argv[i], "multi") == 0)
		read_multi(argc - i - 1, argv + i + 1);
	else if (strcmp(argv[i], "first") == 0)
	{
		show(get_next_line(open_path(argv[i + 1])));
		stats();
		printf("!P\n");
		return (0);
	}
	else
		usage();
	stats();
	lft_check_leaks();
	printf("!P\n");
	return (0);
}
