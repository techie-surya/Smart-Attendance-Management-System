"""
Face Encoding Module
Converts face images into numerical embeddings for recognition
"""

import face_recognition
import pickle
import os
from pathlib import Path
import cv2
from . import config


class FaceEncoder:
    """Generates and saves face encodings from dataset"""
    
    def __init__(self):
        """Initialize face encoder"""
        self.dataset_path = config.DATASET_PATH
        self.encodings_file = config.ENCODINGS_FILE
        self.encoding_model = config.FACE_ENCODING_MODEL
        self.known_encodings = []
        self.known_names = []
        
        # Ensure encodings directory exists
        os.makedirs(os.path.dirname(self.encodings_file), exist_ok=True)
    
    def load_dataset(self):
        """
        Load all images from dataset folder
        Returns list of (image_path, student_id, name)
        """
        print("\n" + "="*60)
        print("LOADING DATASET")
        print("="*60)
        
        image_paths = []
        
        if not os.path.exists(self.dataset_path):
            print(f"Error: Dataset path '{self.dataset_path}' does not exist!")
            return image_paths
        
        # Iterate through student folders
        for student_folder in os.listdir(self.dataset_path):
            folder_path = os.path.join(self.dataset_path, student_folder)
            
            if not os.path.isdir(folder_path):
                continue
            
            # Extract student_id and name from folder name
            # Format: student_001_Debasis
            student_id = student_folder
            
            # Get all image files in folder
            for img_file in os.listdir(folder_path):
                if img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    img_path = os.path.join(folder_path, img_file)
                    image_paths.append((img_path, student_id, student_folder))
        
        print(f"Found {len(image_paths)} images across {len(os.listdir(self.dataset_path))} students")
        return image_paths
    
    def encode_faces(self):
        """
        Process all images and generate face encodings
        Uses HOG with 2x upsample for best speed/quality balance
        """
        print("\n" + "="*60)
        print("GENERATING FACE ENCODINGS")
        print("="*60)
        print(f"Detection Model: HOG (1x upsample for speed/quality balance)")
        print(f"Encoding Model: {self.encoding_model}")
        print("-"*60)
        
        # Load dataset
        image_paths = self.load_dataset()
        
        if not image_paths:
            print("No images found in dataset!")
            return False
        
        total_images = len(image_paths)
        processed = 0
        failed = 0
        
        # Process each image
        for img_path, student_id, student_name in image_paths:
            try:
                # Load image
                image = face_recognition.load_image_file(img_path)
                
                # Use HOG with 1x upsample for speed/quality balance
                # Matches the validation step for consistency
                face_locations = face_recognition.face_locations(
                    image, 
                    model="hog",
                    number_of_times_to_upsample=1  # Consistent with validation
                )
                
                # Generate encodings using the "large" model for best accuracy
                encodings = face_recognition.face_encodings(
                    image, 
                    face_locations,
                    model=self.encoding_model
                )
                
                if len(encodings) > 0:
                    # If multiple faces detected, use the largest one (likely the main subject)
                    if len(encodings) > 1:
                        # Find largest face by area
                        areas = [(bottom - top) * (right - left) for top, right, bottom, left in face_locations]
                        largest_idx = areas.index(max(areas))
                        self.known_encodings.append(encodings[largest_idx])
                        print(f"  ! Multiple faces ({len(encodings)}) in {os.path.basename(img_path)} - using largest")
                    else:
                        self.known_encodings.append(encodings[0])
                    self.known_names.append(student_id)
                    processed += 1
                else:
                    failed += 1
                    print(f"  ✗ No face detected in: {os.path.basename(img_path)}")
                
                # Progress indicator
                progress = (processed + failed) / total_images * 100
                print(f"Processing: {processed + failed}/{total_images} [{progress:.1f}%] - Success: {processed}, Failed: {failed}", end='\r')
                
            except Exception as e:
                failed += 1
                print(f"\n  ✗ Error processing {img_path}: {e}")
        
        print("\n" + "-"*60)
        print(f"Encoding complete: {processed} successful, {failed} failed")
        
        return processed > 0
    
    def load_existing_encodings(self):
        """Load existing encodings from file"""
        if os.path.exists(self.encodings_file):
            try:
                with open(self.encodings_file, 'rb') as f:
                    data = pickle.load(f)
                    return data.get("encodings", []), data.get("names", [])
            except Exception as e:
                print(f"Warning: Could not load existing encodings: {e}")
        return [], []
    
    def save_encodings(self):
        """Save encodings to pickle file"""
        print("\n" + "="*60)
        print("SAVING ENCODINGS")
        print("="*60)
        
        data = {
            "encodings": self.known_encodings,
            "names": self.known_names
        }
        
        try:
            with open(self.encodings_file, 'wb') as f:
                pickle.dump(data, f)
            
            print(f"✓ Encodings saved successfully!")
            print(f"  File: {self.encodings_file}")
            print(f"  Total encodings: {len(self.known_encodings)}")
            print(f"  Unique students: {len(set(self.known_names))}")
            return True
            
        except Exception as e:
            print(f"✗ Error saving encodings: {e}")
            return False
    
    def encode_single_student(self, student_id):
        """Encode faces for a single new student and append to existing encodings.
        This is MUCH faster than re-encoding all students.
        
        Args:
            student_id: The student folder name (e.g., 'student_2301105473_Debasis_Behera')
        
        Returns:
            tuple: (success, num_encoded) - success boolean and number of faces encoded
        """
        print("\n" + "="*60)
        print(f"ENCODING NEW STUDENT: {student_id}")
        print("="*60)
        
        # Load existing encodings
        existing_encodings, existing_names = self.load_existing_encodings()
        
        # If student already has encodings, remove them first (for re-registration)
        if student_id in existing_names:
            print(f"⚠️  Student {student_id} already has encodings - removing old encodings...")
            # Filter out old encodings for this student
            filtered_encodings = []
            filtered_names = []
            removed_count = 0
            
            for encoding, name in zip(existing_encodings, existing_names):
                if name == student_id:
                    removed_count += 1
                else:
                    filtered_encodings.append(encoding)
                    filtered_names.append(name)
            
            existing_encodings = filtered_encodings
            existing_names = filtered_names
            print(f"  Removed {removed_count} old encodings for {student_id}")
        
        student_folder = os.path.join(self.dataset_path, student_id)
        
        if not os.path.exists(student_folder):
            print(f"✗ Student folder not found: {student_folder}")
            return False, 0
        
        # Get all images for this student
        image_files = [f for f in os.listdir(student_folder) 
                      if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        if not image_files:
            print(f"✗ No images found for student {student_id}")
            return False, 0
        
        print(f"Found {len(image_files)} images for {student_id}")
        print("-"*60)
        
        encoded_count = 0
        
        for img_file in image_files:
            try:
                img_path = os.path.join(student_folder, img_file)
                image = face_recognition.load_image_file(img_path)
                
                # Use HOG with 1x upsample matching validation
                face_locations = face_recognition.face_locations(
                    image, 
                    model="hog",
                    number_of_times_to_upsample=1  # Consistent with validation
                )
                
                encodings = face_recognition.face_encodings(
                    image, 
                    face_locations,
                    model=self.encoding_model
                )
                
                if len(encodings) > 0:
                    # Use largest face if multiple detected
                    if len(encodings) > 1:
                        areas = [(bottom - top) * (right - left) 
                                for top, right, bottom, left in face_locations]
                        largest_idx = areas.index(max(areas))
                        existing_encodings.append(encodings[largest_idx])
                    else:
                        existing_encodings.append(encodings[0])
                    
                    existing_names.append(student_id)
                    encoded_count += 1
                    print(f"  ✓ Encoded: {img_file}")
                else:
                    print(f"  ✗ No face in: {img_file}")
                    
            except Exception as e:
                print(f"  ✗ Error processing {img_file}: {e}")
        
        print("-"*60)
        print(f"Encoded {encoded_count}/{len(image_files)} images for {student_id}")
        
        if encoded_count > 0:
            # Save updated encodings
            self.known_encodings = existing_encodings
            self.known_names = existing_names
            success = self.save_encodings()
            return success, encoded_count
        
        return False, 0
    
    def remove_student_encodings(self, student_id):
        """Remove encodings for a deleted student without re-encoding others.
        
        Args:
            student_id: The student ID to remove
        
        Returns:
            bool: Success status
        """
        print("\n" + "="*60)
        print(f"REMOVING ENCODINGS FOR: {student_id}")
        print("="*60)
        
        # Load existing encodings
        existing_encodings, existing_names = self.load_existing_encodings()
        
        if not existing_encodings:
            print("No existing encodings found")
            return True
        
        # Count how many to remove
        count_before = len(existing_names)
        
        # Filter out the student's encodings
        filtered_encodings = []
        filtered_names = []
        removed_count = 0
        
        for encoding, name in zip(existing_encodings, existing_names):
            if name == student_id:
                removed_count += 1
            else:
                filtered_encodings.append(encoding)
                filtered_names.append(name)
        
        print(f"Removed {removed_count} encodings for {student_id}")
        print(f"Remaining: {len(filtered_names)} encodings ({len(set(filtered_names))} students)")
        
        # Save updated encodings
        self.known_encodings = filtered_encodings
        self.known_names = filtered_names
        return self.save_encodings()
    
    def run(self):
        """Main entry point for face encoding"""
        print("\n" + "╔" + "="*58 + "╗")
        print("║" + " "*12 + "FACE ENCODING GENERATION" + " "*22 + "║")
        print("╚" + "="*58 + "╝")
        
        # Check if dataset exists
        if not os.path.exists(self.dataset_path):
            print(f"\n✗ Dataset folder not found: {self.dataset_path}")
            print("  Please run 'collect_face_data.py' first!")
            return False
        
        # Encode faces
        success = self.encode_faces()
        
        if not success:
            print("\n✗ Face encoding failed!")
            return False
        
        # Save encodings
        save_success = self.save_encodings()
        
        if save_success:
            print("\n" + "="*60)
            print("✓ ENCODING PROCESS COMPLETE!")
            print("="*60)
            print("  Next step: Run entry/exit camera systems")
            print("="*60)
            return True
        else:
            return False


def main():
    """Main function"""
    encoder = FaceEncoder()
    encoder.run()


if __name__ == "__main__":
    main()
