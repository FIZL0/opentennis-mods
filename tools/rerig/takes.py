"""Further takes of a mod's reactions (standard §6 `motions`: `re_gu.1`, `re_gu.2`, …; opentennis M130).

A reaction has one clip of the character's own (oob_data.PICK and the like); the game draws its takes in turn, one each
time the reaction starts. TAKES lists, per mod, the source clips beside that one, by the mood of their own face
channels (smile/laugh for the won point and game, anger/sorrow/sad for the lost), all facing the camera at their
start (the shot reactions `re_*_p/wi` begin turned to the ball, 19-81 degrees, so they're left out).
"""

# (game, pc) -> {hst reaction: [source clip, …]}
TAKES = {
    # Out of Bounds Sophie (pc02): her profile's "Play Animation" set and results-screen poses
    ("oob", 2): {
        # ku02_ga is the motion itself
        "re_gu": ["ku02_gl", "ku02_ha", "ku02_cl", "ku02_sh"],  # peace-sign kick, wave, clap, hands to cheeks (laugh/smile)
        # ku02_di is the motion itself
        "re_di": ["ku02_an", "ku02_su"],  # angry stamp, sulk (anger/sorrow)
        # ga_pc02_bi_r00 is the motion itself
        "re_gu_set": ["ga_pc02_bi_r01", "ga_pc02_ea_r00", "ga_pc02_pa_r00", "rslt_win_pc02", "rslt_vict_pc02",
                      "rslt_get_pc02"],  # birdie 2, eagle, par, results win/victory/prize (laugh/smile)
        # ga_pc02_bo_r00 is the motion itself
        "re_di_set": ["rslt_loss_pc02", "rslt_loss_pc02_2"],  # results losses (sorrow/muka)
    },
}


def takes(game, pc):
    """{hst reaction: [source clip, …]} of mod (game, pc), else {}."""
    return TAKES.get((game, pc), {})
