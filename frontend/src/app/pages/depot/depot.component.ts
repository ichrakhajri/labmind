import { Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { LabmindApiService } from '../../services/labmind-api.service';

@Component({
  selector: 'app-depot',
  imports: [RouterLink],
  templateUrl: './depot.component.html',
  styleUrl: './depot.component.css'
})
export class DepotComponent {
  private api = inject(LabmindApiService);
  private router = inject(Router);

  selectedFile: File | null = null;
  isDragging = false;
  isUploading = false;
  localError = '';

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.setFile(input.files[0]);
    }
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    this.isDragging = true;
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    this.isDragging = false;
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragging = false;
    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      this.setFile(event.dataTransfer.files[0]);
    }
  }

  private setFile(file: File) {
    this.localError = '';
    this.selectedFile = file;
  }

  lancerAnalyse() {
    if (!this.selectedFile || this.isUploading) {
      this.localError = 'Veuillez sélectionner un fichier PDF ou une image.';
      return;
    }

    this.isUploading = true;
    this.localError = '';

    this.api.createTask(this.selectedFile).subscribe({
      next: (task) => {
        this.isUploading = false;
        this.router.navigate(['/attente', task.task_id]);
      },
      error: (err) => {
        this.isUploading = false;
        const formatted = this.api.formatError(err);
        this.router.navigate(['/erreur'], { state: { error: formatted } });
      }
    });
  }
}
