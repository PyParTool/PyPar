n_traced = 278
n_scalable = 26

parallelizables = [
    ('~/.local/lib/python3.8/site-packages/seaborn/regression.py', 'regression', '_RegressionPlotter.fit_fast'),
    ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_LVPlotter._lv_box_ends'),
    ('~/.local/lib/python3.8/site-packages/seaborn/utils.py', 'utils', 'iqr'),
    ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_ViolinPlotter.draw_box_lines'),
    ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_CategoricalPlotter._group_longform')
]

funcN = {('~/.local/lib/python3.8/site-packages/seaborn/_statistics.py', '_statistics', 'ECDF._eval_univariate'): 62500093, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', 'violinplot'): 1953224, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_ViolinPlotter.__init__'): 7812599, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_ViolinPlotter.fit_kde'): 250000075, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_ViolinPlotter.draw_box_lines'): 1000000000, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_ViolinPlotter.draw_points'): 250000075, ('~/.local/lib/python3.8/site-packages/seaborn/regression.py', 'regression', '_RegressionPlotter.fit_fast'): 1000000000, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_BarPlotter.__init__'): 1953224, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_CategoricalPlotter._group_longform'): 125000087, ('~/.local/lib/python3.8/site-packages/seaborn/matrix.py', 'matrix', '_HeatMapper.__init__'): 1000000000, ('~/.local/lib/python3.8/site-packages/seaborn/matrix.py', 'matrix', '_HeatMapper._skip_ticks'): 1000000000, ('~/.local/lib/python3.8/site-packages/seaborn/utils.py', 'utils', 'ci'): 250000075, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_LVPlotter._lv_box_ends'): 15625098, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_LVPlotter._lv_outliers'): 500000050, ('~/.local/lib/python3.8/site-packages/seaborn/regression.py', 'regression', 'residplot'): 15358, ('~/.local/lib/python3.8/site-packages/seaborn/regression.py', 'regression', '_RegressionPlotter.fit_statsmodels'): 976662, ('~/.local/lib/python3.8/site-packages/seaborn/distributions.py', 'distributions', '_DistributionPlotter._quantile_to_level'): 62500093, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_ViolinPlotter.draw_quartiles'): 1000000000, ('~/.local/lib/python3.8/site-packages/seaborn/matrix.py', 'matrix', 'dendrogram'): 7812599, ('~/.local/lib/python3.8/site-packages/seaborn/matrix.py', 'matrix', '_DendrogramPlotter.__init__'): 7812599, ('~/.local/lib/python3.8/site-packages/seaborn/algorithms.py', 'algorithms', '_structured_bootstrap'): 244240, ('~/.local/lib/python3.8/site-packages/seaborn/categorical.py', 'categorical', '_ViolinPlotter.draw_stick_lines'): 31250096, ('~/.local/lib/python3.8/site-packages/seaborn/regression.py', 'regression', '_RegressionPlotter.fit_poly'): 3906349, ('~/.local/lib/python3.8/site-packages/seaborn/regression.py', 'regression', '_RegressionPlotter.regress_out'): 500000050, ('~/.local/lib/python3.8/site-packages/seaborn/utils.py', 'utils', 'pmf_hist'): 1000000000, ('~/.local/lib/python3.8/site-packages/seaborn/utils.py', 'utils', 'iqr'): 125000087}

import numpy as np
from seaborn.regression import _RegressionPlotter
x = np.zeros(shape= (1 * 10 ** 8, ))
y = np.zeros(shape= (1 * 10 ** 8, ))
grid = np.zeros(shape= (1 * 10 ** 8, ))
plotter = _RegressionPlotter(x=x, y=y, ci=None)

funcInput = {
    ('~/.local/lib/python3.8/site-packages/seaborn/regression.py', 'regression', '_RegressionPlotter.fit_fast'): 
        ([], {'self': plotter, 'grid': grid})
}
