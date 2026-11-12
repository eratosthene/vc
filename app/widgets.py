from flask_appbuilder.widgets import FormWidget, ListWidget, RenderTemplateWidget


class CollectionModelListWidget(ListWidget):
    template = "widgets/cmlw.html"


class CategorizeListWidget(ListWidget):
    """The Categorize list: its rows open the edit form in a modal."""

    template = "widgets/categorize_list.html"


class CategorizeRowWidget(RenderTemplateWidget):
    """One row of the Categorize list, for the modal to swap in after a save."""

    template = "widgets/categorize_row.html"


class CategorizeFormWidget(FormWidget):
    """The edit form without its Save and Back buttons, which the modal has."""

    template = "widgets/categorize_form.html"
