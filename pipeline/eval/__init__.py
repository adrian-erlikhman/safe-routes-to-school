"""Out-of-sample evaluation of the risk model.

`validate.py` proves the router is correct *given* the risk surface. Nothing in
it tests whether the risk surface predicts anything, because exposure is
defined by the same model being checked -- a model that scored blocks at random
would pass it just as well. These scripts test the surface against data it was
never fitted on.
"""
