# 3rd party
from domdf_python_tools import stringlist
from sphinx.application import Sphinx  # nodep
from sphinx.config import Config  # nodep


def configure(app: Sphinx, config: Config):
	"""
	Configure :mod:`sphinx_toolbox_experimental.autosummary_widths`.

	:param app: The Sphinx application.
	:param config:
	"""

	latex_elements = getattr(config, "latex_elements", {})

	latex_preamble = stringlist.StringList(latex_elements.get("preamble", ''))
	latex_preamble.blankline()
	latex_preamble.append(r"\makeatletter")
	latex_preamble.append(r"\newcolumntype{\Xx}[2]{>{\raggedright\arraybackslash}p{\dimexpr")
	latex_preamble.append(r"    (\linewidth-\arrayrulewidth)*#1/#2-\tw@\tabcolsep-\arrayrulewidth\relax}}")
	latex_preamble.append(r"\makeatother")
	latex_preamble.blankline()

	latex_elements["preamble"] = str(latex_preamble)
	config.latex_elements = latex_elements  # type: ignore


def setup(app: Sphinx):
	app.connect("config-inited", configure)
