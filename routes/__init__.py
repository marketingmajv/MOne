"""
M-One Routes Package (Flask Blueprints)
Centraliza o registro de todos os módulos de rotas e garante retrocompatibilidade total.
"""

from routes.auth_routes import auth_bp
from routes.dashboard_routes import dashboard_bp
from routes.sales_routes import sales_bp
from routes.stock_routes import stock_bp
from routes.freight_routes import freight_bp
from routes.finance_routes import finance_bp
from routes.crm_routes import crm_bp
from routes.webhook_routes import webhook_bp
from routes.product_routes import product_bp
from routes.import_routes import import_bp
from routes.bling_routes import bling_bp
from routes.copilot_routes import copilot_bp
from routes.user_routes import user_bp

ALL_BLUEPRINTS = [
    auth_bp,
    dashboard_bp,
    sales_bp,
    stock_bp,
    freight_bp,
    finance_bp,
    crm_bp,
    webhook_bp,
    product_bp,
    import_bp,
    bling_bp,
    copilot_bp,
    user_bp,
]


def register_blueprints(app):
    """Registra todos os blueprints e cria aliases de endpoint para compatibilidade total."""
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # Injetar aliases curtos (ex: 'sales' -> 'sales.sales') para compatibilidade de url_for nos templates legados
    for rule in list(app.url_map.iter_rules()):
        if "." in rule.endpoint:
            short_name = rule.endpoint.split(".", 1)[1]
            if short_name not in app.view_functions:
                app.add_url_rule(
                    rule.rule,
                    endpoint=short_name,
                    view_func=app.view_functions[rule.endpoint],
                    methods=rule.methods,
                )
