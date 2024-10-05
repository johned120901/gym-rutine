from flask import Flask, request, jsonify, session, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

app = Flask(__name__)  # Inicializar la aplicación Flask
app.secret_key = 'your_secret_key'  # Clave secreta para gestionar sesiones
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gym_rutine.db'  # Configuración de la base de datos SQLite
db = SQLAlchemy(app)  # Inicializar SQLAlchemy con la aplicación

# Inicializar Flask-Login para gestionar la autenticación de usuarios
login_manager = LoginManager()
login_manager.init_app(app)  # Asociar Flask-Login con la aplicación
login_manager.login_view = 'login'  # Ruta que se usará para el inicio de sesión

# Modelo de usuario
class User(UserMixin, db.Model):
    __tablename__ = 'user'  # Nombre de la tabla en la base de datos
    id = db.Column(db.Integer, primary_key=True)  # ID único para cada usuario
    username = db.Column(db.String, nullable=False, unique=True)  # Nombre de usuario único
    password = db.Column(db.String, nullable=False)  # Contraseña del usuario

    favorites = relationship("Favorite", back_populates="user")  # Relación con la tabla de favoritos
    routines = relationship("Routine", back_populates="user")  # Relación con la tabla de rutinas

# Modelo de rutina
class Routine(db.Model):
    __tablename__ = 'routine'  # Nombre de la tabla en la base de datos
    id = db.Column(db.Integer, primary_key=True)  # ID único para cada rutina
    routine_name = db.Column(db.String, nullable=False)  # Nombre de la rutina
    user_id = db.Column(db.Integer, ForeignKey('user.id'))  # ID del usuario que creó la rutina
    
    # Relación con ejercicios y favoritos; se utilizan cascadas para manejar eliminación
    exercises = relationship("Exercise", back_populates="routine", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="routine", cascade="all, delete-orphan")
    user = relationship("User", back_populates="routines")  # Relación con el usuario

# Modelo de ejercicio
class Exercise(db.Model):
    __tablename__ = 'exercise'  # Nombre de la tabla en la base de datos
    id = db.Column(db.Integer, primary_key=True)  # ID único para cada ejercicio
    name = db.Column(db.String(100), nullable=False)  # Nombre del ejercicio
    sets = db.Column(db.Integer, nullable=False)  # Número de series
    reps = db.Column(db.Integer, nullable=False)  # Número de repeticiones
    routine_id = db.Column(db.Integer, db.ForeignKey('routine.id'), nullable=False)  # ID de la rutina a la que pertenece

    routine = relationship("Routine", back_populates="exercises")  # Relación con la rutina

# Modelo de favoritos
class Favorite(db.Model):
    __tablename__ = 'favorite'  # Nombre de la tabla en la base de datos
    id = db.Column(db.Integer, primary_key=True)  # ID único para cada favorito
    user_id = db.Column(db.Integer, ForeignKey('user.id'), nullable=False)  # ID del usuario
    routine_id = db.Column(db.Integer, ForeignKey('routine.id'), nullable=False)  # ID de la rutina favorita

    user = relationship("User", back_populates="favorites")  # Relación con el usuario
    routine = relationship("Routine", back_populates="favorites")  # Relación con la rutina

# Función de carga del usuario
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # Cargar el usuario a partir de su ID

with app.app_context():
    db.create_all()  # Crear todas las tablas en la base de datos

@app.route('/')
def home():
    return render_template('index.html')  # Renderizar la plantilla de la página de inicio

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = current_user.id  # Obtener el ID del usuario actual

    routines = get_user_routines(user_id)  # Obtener rutinas del usuario
    favorites = get_user_favorites(user_id)  # Obtener rutinas favoritas del usuario

    return render_template('dashboard.html', routines=routines, favorites=favorites)  # Renderizar el dashboard

@app.route('/public_routines')
@login_required
def view_public_routines():
    current_user_id = current_user.id  # ID del usuario actual
    # Obtener rutinas que no sean del usuario actual
    routines = Routine.query.filter(Routine.user_id != current_user_id).all()
    
    # Obtener una lista de IDs de rutinas favoritas del usuario actual
    user_favorites = [routine.id for routine in current_user.favorites]
    
    return render_template('public_routines.html', routines=routines, user_favorites=user_favorites)  # Renderizar rutinas públicas

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json  # Obtener datos del formulario de registro
        hashed_password = generate_password_hash(data['password'])  # Generar un hash de la contraseña
        new_user = User(username=data['username'], password=hashed_password)  # Crear un nuevo usuario
        db.session.add(new_user)  # Agregar el nuevo usuario a la sesión
        db.session.commit()  # Confirmar cambios en la base de datos
        return jsonify(success=True)  # Responder con éxito
    return render_template('register.html')  # Renderizar la plantilla de registro

@app.route('/login', methods=['POST'])
def login():
    data = request.json  # Obtener datos del formulario de inicio de sesión
    user = User.query.filter_by(username=data['username']).first()  # Buscar usuario por nombre de usuario
    if user and check_password_hash(user.password, data['password']):  # Verificar contraseña
        login_user(user)  # Iniciar sesión del usuario
        session['username'] = user.username  # Almacenar el nombre de usuario en la sesión
        return jsonify(success=True)  # Responder con éxito
    return jsonify(success=False)  # Responder con fallo

@app.route('/add_routine', methods=['POST'])
@login_required
def add_routine():
    if 'username' not in session:  # Verificar si el usuario está autenticado
        return jsonify(success=False, message="User not logged in"), 401

    current_user = User.query.filter_by(username=session['username']).first()  # Obtener usuario actual
    
    try:
        data = request.json  # Obtener datos de la rutina
        print(f"Received data: {data}")  # Línea de depuración

        if 'routine_name' not in data or 'exercises' not in data:  # Validar datos recibidos
            return jsonify(success=False, message="Missing data"), 400

        new_routine = Routine(
            user_id=current_user.id, 
            routine_name=data['routine_name']
        )  # Crear nueva rutina
        db.session.add(new_routine)  # Agregar rutina a la sesión
        db.session.commit()  # Confirmar cambios en la base de datos

        # Agregar los ejercicios a la rutina
        for exercise in data['exercises']:
            new_exercise = Exercise(
                name=exercise['name'],
                sets=exercise['sets'],
                reps=exercise['reps'],
                routine_id=new_routine.id  # Asignar la rutina al ejercicio
            )
            db.session.add(new_exercise)  # Agregar ejercicio a la sesión

        db.session.commit()  # Confirmar cambios en la base de datos

        return jsonify(success=True)  # Responder con éxito
    except Exception as e:
        print(f"Error: {e}")  # Imprimir mensaje de error en la consola
        return jsonify(success=False, message="Error adding routine"), 500  # Responder con error

@app.route('/get_routines', methods=['GET'])
@login_required
def get_routines():
    routines = Routine.query.filter_by(user_id=current_user.id).all()  # Obtener rutinas del usuario actual
    routine_list = []
    for routine in routines:
        # Crear una lista de diccionarios con los ejercicios de la rutina
        exercises = [{'name': ex.name, 'sets': ex.sets, 'reps': ex.reps} for ex in routine.exercises]
        routine_list.append({
            'id': routine.id,
            'routine_name': routine.routine_name,
            'exercises': exercises  # Incluir los ejercicios en la respuesta
        })
    return jsonify(routines=routine_list)  # Devolver rutinas en formato JSON

@app.route('/edit_routine/<int:routine_id>', methods=['GET', 'POST'])
@login_required
def edit_routine(routine_id):
    # Obtener la rutina que se va a editar
    routine = Routine.query.filter_by(id=routine_id, user_id=current_user.id).first()  # Buscar rutina por ID
    if not routine:
        return jsonify(success=False, message="Rutina no encontrada o no tienes permiso para modificarla"), 404  # Responder con error si no existe

    if request.method == 'POST':
        # Si se envía el formulario, actualiza la rutina
        data = request.json
        routine.routine_name = data['routine_name']  # Actualizar el nombre de la rutina
        
        # Borrar ejercicios anteriores
        Exercise.query.filter_by(routine_id=routine.id).delete()  # Eliminar ejercicios antiguos

        # Agregar nuevos ejercicios
        for exercise in data['exercises']:
            new_exercise = Exercise(
                name=exercise['name'],
                sets=exercise['sets'],
                reps=exercise['reps'],
                routine_id=routine.id  # Asignar la rutina al ejercicio
            )
            db.session.add(new_exercise)  # Agregar ejercicio a la sesión

        db.session.commit()  # Confirmar cambios en la base de datos
        return jsonify(success=True, message="Rutina actualizada correctamente")  # Responder con éxito

    # Renderizar la plantilla de edición de rutina
    return render_template('edit_routine.html', routine=routine)  # Devolver la plantilla para editar

@app.route('/delete_routine/<int:routine_id>', methods=['POST'])
@login_required
def delete_routine(routine_id):
    # Buscar la rutina por ID y verificar que el usuario sea el creador
    routine = Routine.query.filter_by(id=routine_id, user_id=current_user.id).first()  # Buscar rutina por ID
    if not routine:
        return jsonify(success=False, message="Rutina no encontrada o no tienes permiso para eliminarla"), 404  # Responder con error si no existe

    # Eliminar los ejercicios asociados
    for exercise in routine.exercises:
        db.session.delete(exercise)  # Eliminar cada ejercicio

    # Eliminar la rutina
    db.session.delete(routine)  # Eliminar rutina
    db.session.commit()  # Confirmar cambios en la base de datos
    return jsonify(success=True, message="Rutina eliminada correctamente")  # Responder con éxito

@app.route('/favorite/<int:routine_id>', methods=['POST'])
@login_required
def toggle_favorite(routine_id):
    # Verificar si la rutina ya es un favorito
    favorite = Favorite.query.filter_by(user_id=current_user.id, routine_id=routine_id).first()
    if favorite:
        db.session.delete(favorite)  # Quitar de favoritos
        message = "Rutina quitada de favoritos"
    else:
        new_favorite = Favorite(user_id=current_user.id, routine_id=routine_id)  # Crear nuevo favorito
        db.session.add(new_favorite)  # Agregar a favoritos
        message = "Rutina marcada como favorita"

    db.session.commit()  # Confirmar cambios en la base de datos
    return jsonify(success=True, message=message)  # Responder con éxito

def get_user_routines(user_id):
    """Obtiene las rutinas de un usuario específico."""
    return Routine.query.filter_by(user_id=user_id).all()  # Devolver rutinas del usuario

def get_user_favorites(user_id):
    """Obtiene las rutinas favoritas de un usuario específico."""
    favorites = Favorite.query.filter_by(user_id=user_id).all()  # Obtener favoritos del usuario
    return [favorite.routine for favorite in favorites]  # Devolver las rutinas favoritas

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Crear las tablas si no existen
    app.run(debug=True)  # Iniciar la aplicación en modo de depuración
