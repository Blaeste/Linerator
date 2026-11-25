/* A fake get_next_line for the tests of Linerator: it reads with stdio (fdopen, getc),
** functions the subject forbids, so it can never be handed in. Each line is
** built in memory from malloc, like a real one. FAKE_MODE breaks it in one way:
**   0 good   1 leaks   2 no terminator   3 no newline   4 crash on a long line
**   5 a buffer of BUFFER_SIZE on the stack   6 reads the whole file first
**   7 sees a failed read()                   8 one static too many */
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "get_next_line.h"

#ifndef FAKE_MODE
# define FAKE_MODE 0
#endif
#ifndef BUFFER_SIZE
# define BUFFER_SIZE 42
#endif

static char	*grow(char *line, size_t len, size_t *cap)
{
	char	*bigger;

	*cap = *cap * 2 + 16;
	bigger = malloc(*cap);
	if (bigger == NULL)
	{
		free(line);
		return (NULL);
	}
	if (line)
		memcpy(bigger, line, len);
	free(line);
	return (bigger);
}

char	*get_next_line(int fd)
{
	static FILE	*files[1024];
	char		*line;
	size_t		len;
	size_t		cap;
	int			c;

#if FAKE_MODE == 8
	static int	second;

	second++;
#endif
#if FAKE_MODE == 5
	volatile char	stack[BUFFER_SIZE];

	stack[0] = 0;
	stack[BUFFER_SIZE - 1] = 0;
#endif
#if FAKE_MODE == 7
	char	probe;

	if (fd >= 0 && fd < 1024 && read(fd, &probe, 0) < 0)
	{
		if (files[fd])
			fclose(files[fd]);
		files[fd] = NULL;
		return (NULL);
	}
#endif
	if (fd < 0 || fd >= 1024)
		return (NULL);
	/* A closed fd: NULL, and what was kept for it is dropped. */
	if (fcntl(fd, F_GETFD) < 0)
	{
		if (files[fd])
			fclose(files[fd]);
		files[fd] = NULL;
		return (NULL);
	}
#if FAKE_MODE == 6
	if (files[fd] == NULL)
	{
		char	*all = malloc(1 << 20);

		while (all && read(fd, all, 1 << 20) > 0)
			;
		free(all);
		lseek(fd, 0, SEEK_SET);
	}
#endif
	if (files[fd] == NULL)
		files[fd] = fdopen(dup(fd), "r");
	if (files[fd] == NULL)
		return (NULL);
	line = NULL;
	len = 0;
	cap = 0;
	while ((c = getc(files[fd])) != EOF)
	{
		if (len + 2 > cap && (line = grow(line, len, &cap)) == NULL)
			return (NULL);
		if (c == '\n' && FAKE_MODE == 3)
			break ;
		line[len++] = (char)c;
		if (c == '\n')
			break ;
	}
	if (len == 0)
	{
		free(line);
		return (NULL);
	}
	if (FAKE_MODE == 4 && len > 1000)
		*(volatile char *)0 = 0;
	if (FAKE_MODE == 1)
		malloc(16);
	if (FAKE_MODE == 2)
	{
		char	*exact = malloc(len);

		memcpy(exact, line, len);
		free(line);
		return (exact);
	}
	line[len] = '\0';
	return (line);
}
