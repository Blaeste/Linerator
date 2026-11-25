/* What the test program of Linerator shares with the memory engine of libfterator. */
#ifndef LINERATOR_H
# define LINERATOR_H

# include <stddef.h>
# include <sys/types.h>

/* 1 for English messages (the default), 0 for French (--lang fr). */
extern int	lft_en;

# define TR(fr, en) (lft_en ? (en) : (fr))

/* The function under test, from the files of the student. */
char	*get_next_line(int fd);

/* The memory engine (alloc.c). */
void	lft_fail_malloc_at(long call);
long	lft_malloc_calls(void);
long	lft_live_blocks(void);
void	lft_check_leaks(void);

#endif
