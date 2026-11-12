"""What the tests share: one actor in a film, and building a figure at moments of the acting."""
from characters import film

ACTIONS = film.can("bear")["actions"]     # what every plush character can play (a robot has "screen-icon" besides)
ALIGNMENT = {"characters": list("ola bom dia"),
             "character_start_times_seconds": [0.09 * i for i in range(11)],
             "character_end_times_seconds": [0.09 * i + 0.09 for i in range(11)]}


def drawn(f: film.Film, actor: film.Actor, times) -> int:
    """Builds the actor's figure as the film's keys have it at each time; gives how many parts it drew."""
    track = f.loc.motion[id(actor.fig)]
    parts = 0
    for t in times:
        parts += len(actor.fig.posed(dict(track.at(t))).build())
    return parts


def one(who: str, pose: str = "idle", fps: int = 12) -> tuple[film.Film, film.Actor]:
    f = film.Film("test", size=(320, 320), fps=fps)
    actor = f.add(who, pose)
    f.camera((0, 1, 10), look_at=(0, 0.4, 0), lens=80)
    return f, actor
