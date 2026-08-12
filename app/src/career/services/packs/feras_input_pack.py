from . import register

@register('feras')
def build(application_id, db):
    app = db.fetch_one("SELECT * FROM applications WHERE id = ?", (application_id,))
    if not app:
        return {'error': 'Application not found'}
    return {
        'application_id': application_id,
        'company': app['company'],
        'role': app['role'],
        'score': app['score'],
        'cv_language': app['cv_language'],
    }
