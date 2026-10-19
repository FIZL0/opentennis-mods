"""Further takes of a mod's reactions (standard §6 `motions`: `re_gu.1`, `re_gu.2`, …; opentennis M130).

A reaction has one clip of the character's own (oob_data.PICK and the like); the game draws its takes in turn, one each
time the reaction starts. TAKES lists, per mod, the source clips beside that one, by the mood of their own face
channels (smile/laugh for the won point and game, anger/sorrow/sad for the lost), all facing the camera at their
start.
"""

# (game, pc) -> {hst reaction: [source clip, …]}
TAKES = {
    ("oob", 2): {
        "re_gu": ["ku02_gl", "ku02_ha", "ku02_cl", "ku02_sh"],
        "re_di": ["ku02_an", "ku02_su"],
        "re_gu_set": ["ga_pc02_bi_r01", "ga_pc02_ea_r00", "ga_pc02_pa_r00", "rslt_win_pc02", "rslt_vict_pc02",
                      "rslt_get_pc02"],
        "re_di_set": ["rslt_loss_pc02", "rslt_loss_pc02_2"],
    },
}


def takes(game, pc):
    """{hst reaction: [source clip, …]} of mod (game, pc), else {}."""
    return TAKES.get((game, pc), {})
