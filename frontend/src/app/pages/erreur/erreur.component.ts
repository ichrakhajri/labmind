import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-erreur',
  imports: [RouterLink],
  templateUrl: './erreur.component.html',
  styleUrl: './erreur.component.css'
})
export class ErreurComponent implements OnInit {
  errorCode = '';
  errorMessage =
    "Le document est peut-être illisible ou l'analyse a expiré.";

  ngOnInit() {
    const err = history.state?.error;
    if (err) {
      this.errorCode = err.code || '';
      this.errorMessage = err.message || this.errorMessage;
    }
  }
}
