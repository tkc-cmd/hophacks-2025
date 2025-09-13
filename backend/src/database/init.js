import sqlite3 from 'sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DB_PATH = process.env.DATABASE_PATH || path.join(__dirname, '../../../database/pharmacy.db');

let db;

export function getDatabase() {
  if (!db) {
    throw new Error('Database not initialized. Call initializeDatabase() first.');
  }
  return db;
}

export async function initializeDatabase() {
  return new Promise((resolve, reject) => {
    db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) {
        console.error('Error opening database:', err);
        reject(err);
        return;
      }
      console.log('Connected to SQLite database');
      
      // Create tables and seed data
      createTables()
        .then(() => seedData())
        .then(() => resolve())
        .catch(reject);
    });
  });
}

async function createTables() {
  return new Promise((resolve, reject) => {
    const createPatientsTable = `
      CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        date_of_birth TEXT NOT NULL,
        phone TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `;

    const createPrescriptionsTable = `
      CREATE TABLE IF NOT EXISTS prescriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        medication_name TEXT NOT NULL,
        dosage TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        refills_remaining INTEGER NOT NULL,
        prescriber TEXT NOT NULL,
        last_filled DATE,
        prescribed_date DATE NOT NULL,
        expires_date DATE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients (id)
      )
    `;

    db.serialize(() => {
      db.run(createPatientsTable, (err) => {
        if (err) {
          reject(err);
          return;
        }
      });

      db.run(createPrescriptionsTable, (err) => {
        if (err) {
          reject(err);
          return;
        }
        resolve();
      });
    });
  });
}

async function seedData() {
  return new Promise((resolve, reject) => {
    // Check if data already exists
    db.get("SELECT COUNT(*) as count FROM patients", (err, row) => {
      if (err) {
        reject(err);
        return;
      }

      if (row.count > 0) {
        console.log('Database already seeded');
        resolve();
        return;
      }

      console.log('Seeding database with mock data...');
      
      const patients = [
        { first_name: 'John', last_name: 'Smith', date_of_birth: '1965-05-15', phone: '555-0101' },
        { first_name: 'Mary', last_name: 'Johnson', date_of_birth: '1972-08-22', phone: '555-0102' },
        { first_name: 'Robert', last_name: 'Williams', date_of_birth: '1958-12-03', phone: '555-0103' },
        { first_name: 'Patricia', last_name: 'Brown', date_of_birth: '1980-03-17', phone: '555-0104' },
        { first_name: 'Michael', last_name: 'Davis', date_of_birth: '1945-09-28', phone: '555-0105' },
        { first_name: 'Linda', last_name: 'Miller', date_of_birth: '1963-11-12', phone: '555-0106' },
        { first_name: 'William', last_name: 'Wilson', date_of_birth: '1975-06-08', phone: '555-0107' },
        { first_name: 'Elizabeth', last_name: 'Moore', date_of_birth: '1988-01-25', phone: '555-0108' },
        { first_name: 'David', last_name: 'Taylor', date_of_birth: '1952-04-14', phone: '555-0109' },
        { first_name: 'Barbara', last_name: 'Anderson', date_of_birth: '1967-10-30', phone: '555-0110' }
      ];

      const insertPatient = db.prepare("INSERT INTO patients (first_name, last_name, date_of_birth, phone) VALUES (?, ?, ?, ?)");
      
      patients.forEach(patient => {
        insertPatient.run(patient.first_name, patient.last_name, patient.date_of_birth, patient.phone);
      });
      
      insertPatient.finalize();

      // Seed prescriptions
      const prescriptions = [
        // John Smith (patient_id: 1)
        { patient_id: 1, medication_name: 'Metformin', dosage: '500mg', quantity: 60, refills_remaining: 3, prescriber: 'Dr. Anderson', last_filled: '2024-08-15', prescribed_date: '2024-05-15', expires_date: '2025-05-15' },
        { patient_id: 1, medication_name: 'Lisinopril', dosage: '10mg', quantity: 30, refills_remaining: 2, prescriber: 'Dr. Anderson', last_filled: '2024-08-15', prescribed_date: '2024-05-15', expires_date: '2025-05-15' },
        { patient_id: 1, medication_name: 'Atorvastatin', dosage: '20mg', quantity: 30, refills_remaining: 1, prescriber: 'Dr. Anderson', last_filled: '2024-07-20', prescribed_date: '2024-04-20', expires_date: '2025-04-20' },
        
        // Mary Johnson (patient_id: 2)
        { patient_id: 2, medication_name: 'Levothyroxine', dosage: '75mcg', quantity: 30, refills_remaining: 5, prescriber: 'Dr. Smith', last_filled: '2024-08-10', prescribed_date: '2024-06-10', expires_date: '2025-06-10' },
        { patient_id: 2, medication_name: 'Amlodipine', dosage: '5mg', quantity: 30, refills_remaining: 4, prescriber: 'Dr. Smith', last_filled: '2024-08-10', prescribed_date: '2024-06-10', expires_date: '2025-06-10' },
        { patient_id: 2, medication_name: 'Omeprazole', dosage: '20mg', quantity: 30, refills_remaining: 0, prescriber: 'Dr. Smith', last_filled: '2024-06-10', prescribed_date: '2024-03-10', expires_date: '2024-09-10' },
        
        // Robert Williams (patient_id: 3)
        { patient_id: 3, medication_name: 'Warfarin', dosage: '5mg', quantity: 30, refills_remaining: 2, prescriber: 'Dr. Johnson', last_filled: '2024-08-20', prescribed_date: '2024-07-20', expires_date: '2025-07-20' },
        { patient_id: 3, medication_name: 'Furosemide', dosage: '40mg', quantity: 30, refills_remaining: 3, prescriber: 'Dr. Johnson', last_filled: '2024-08-20', prescribed_date: '2024-07-20', expires_date: '2025-07-20' },
        
        // Patricia Brown (patient_id: 4)
        { patient_id: 4, medication_name: 'Sertraline', dosage: '50mg', quantity: 30, refills_remaining: 5, prescriber: 'Dr. Wilson', last_filled: '2024-08-05', prescribed_date: '2024-06-05', expires_date: '2025-06-05' },
        { patient_id: 4, medication_name: 'Ibuprofen', dosage: '600mg', quantity: 60, refills_remaining: 1, prescriber: 'Dr. Wilson', last_filled: '2024-07-15', prescribed_date: '2024-04-15', expires_date: '2025-04-15' },
        
        // Michael Davis (patient_id: 5)
        { patient_id: 5, medication_name: 'Insulin Glargine', dosage: '100 units/mL', quantity: 1, refills_remaining: 2, prescriber: 'Dr. Brown', last_filled: '2024-08-25', prescribed_date: '2024-07-25', expires_date: '2025-07-25' },
        { patient_id: 5, medication_name: 'Metoprolol', dosage: '50mg', quantity: 60, refills_remaining: 4, prescriber: 'Dr. Brown', last_filled: '2024-08-25', prescribed_date: '2024-07-25', expires_date: '2025-07-25' },
        { patient_id: 5, medication_name: 'Aspirin', dosage: '81mg', quantity: 30, refills_remaining: 0, prescriber: 'Dr. Brown', last_filled: '2024-05-25', prescribed_date: '2024-02-25', expires_date: '2024-08-25' },
        
        // Linda Miller (patient_id: 6)
        { patient_id: 6, medication_name: 'Prednisone', dosage: '10mg', quantity: 30, refills_remaining: 1, prescriber: 'Dr. Davis', last_filled: '2024-08-12', prescribed_date: '2024-06-12', expires_date: '2025-06-12' },
        { patient_id: 6, medication_name: 'Albuterol', dosage: '90mcg', quantity: 1, refills_remaining: 3, prescriber: 'Dr. Davis', last_filled: '2024-07-30', prescribed_date: '2024-05-30', expires_date: '2025-05-30' },
        
        // William Wilson (patient_id: 7)
        { patient_id: 7, medication_name: 'Gabapentin', dosage: '300mg', quantity: 90, refills_remaining: 2, prescriber: 'Dr. Miller', last_filled: '2024-08-18', prescribed_date: '2024-06-18', expires_date: '2025-06-18' },
        { patient_id: 7, medication_name: 'Tramadol', dosage: '50mg', quantity: 30, refills_remaining: 0, prescriber: 'Dr. Miller', last_filled: '2024-06-18', prescribed_date: '2024-03-18', expires_date: '2024-09-18' },
        
        // Elizabeth Moore (patient_id: 8)
        { patient_id: 8, medication_name: 'Montelukast', dosage: '10mg', quantity: 30, refills_remaining: 5, prescriber: 'Dr. Taylor', last_filled: '2024-08-08', prescribed_date: '2024-06-08', expires_date: '2025-06-08' },
        { patient_id: 8, medication_name: 'Loratadine', dosage: '10mg', quantity: 30, refills_remaining: 4, prescriber: 'Dr. Taylor', last_filled: '2024-08-08', prescribed_date: '2024-06-08', expires_date: '2025-06-08' },
        
        // David Taylor (patient_id: 9)
        { patient_id: 9, medication_name: 'Digoxin', dosage: '0.25mg', quantity: 30, refills_remaining: 3, prescriber: 'Dr. Anderson', last_filled: '2024-08-22', prescribed_date: '2024-07-22', expires_date: '2025-07-22' },
        { patient_id: 9, medication_name: 'Clopidogrel', dosage: '75mg', quantity: 30, refills_remaining: 2, prescriber: 'Dr. Anderson', last_filled: '2024-08-22', prescribed_date: '2024-07-22', expires_date: '2025-07-22' },
        
        // Barbara Anderson (patient_id: 10)
        { patient_id: 10, medication_name: 'Simvastatin', dosage: '40mg', quantity: 30, refills_remaining: 1, prescriber: 'Dr. Wilson', last_filled: '2024-08-14', prescribed_date: '2024-05-14', expires_date: '2025-05-14' },
        { patient_id: 10, medication_name: 'Hydrochlorothiazide', dosage: '25mg', quantity: 30, refills_remaining: 3, prescriber: 'Dr. Wilson', last_filled: '2024-08-14', prescribed_date: '2024-05-14', expires_date: '2025-05-14' }
      ];

      const insertPrescription = db.prepare(`
        INSERT INTO prescriptions 
        (patient_id, medication_name, dosage, quantity, refills_remaining, prescriber, last_filled, prescribed_date, expires_date) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);
      
      prescriptions.forEach(prescription => {
        insertPrescription.run(
          prescription.patient_id,
          prescription.medication_name,
          prescription.dosage,
          prescription.quantity,
          prescription.refills_remaining,
          prescription.prescriber,
          prescription.last_filled,
          prescription.prescribed_date,
          prescription.expires_date
        );
      });
      
      insertPrescription.finalize();
      
      console.log('Database seeded successfully');
      resolve();
    });
  });
}

