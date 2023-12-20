# class GameRules:
#     def __init__(self, card_min_rank, card_max_rank, rank_to_value, rank_to_point):
#         self.CARD_MIN_RANK = (card_min_rank,)
#         self.CARD_MAX_RANK = (card_max_rank,)
#         self.RANK_TO_VALUE = (rank_to_value,)
#         self.RANK_TO_POINT = rank_to_point


# MARAFONE_MIN_RANK = 1
# MARAFONE_MAX_RANK = 10

# marafone_values = {
#     i: i + MARAFONE_MAX_RANK if i in [1, 2, 3] else i
#     for i in range(MARAFONE_MIN_RANK, MARAFONE_MAX_RANK + 1)
# }
# marafone_points = {
#     i: 1 if i == 1 else 0.33 if i in [2, 3, 8, 9, 10] else 0
#     for i in range(MARAFONE_MIN_RANK, MARAFONE_MAX_RANK + 1)
# }

# marafone_rules = GameRules(
#     MARAFONE_MIN_RANK, MARAFONE_MAX_RANK, marafone_values, marafone_points
# )
