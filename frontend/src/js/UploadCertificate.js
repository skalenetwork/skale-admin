import React from 'react'
import {withRouter} from 'react-router-dom';

import {Container} from 'reactstrap';
import Button from './SkaleButton/SkaleButton';

import PageTitle from "./shared_components/PageTitle";
import CardTitle from "./shared_components/CardTitle";
import SkInput from "./shared_components/SkInput";

class UploadCertificate extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      name: ''
    };
    this.uploadCertificate = this.uploadCertificate.bind(this);
    this.setCertName = this.setCertName.bind(this);
  }

  setCertName(value) {
    this.setState({name: value});
  }

  uploadCertificate() {
    let form = document.querySelector('form');
    let formData = new FormData(form);
    formData.append('name', this.state.name);

    this.props.history.push('/security');
    fetch('/upload-certificate', {
      method: 'POST',
      body: formData,

    }).then(function (response) {
      return response.text()
    }, function (error) {
      console.error(error.message);
    })
  }

  render() {
    return (
      <Container>
        <div className="marg-30">
          <PageTitle
            title="Upload SSL certificate"
            nopadd={true}
          />
          <div className="new-card marg-bott-30 padd-30 marg-top-30">
            <CardTitle icon="lock" color="neon-green" text="SSL certificate"/>

            <div className="card-content">
              <form className="form-wrap" style={{maxWidth: "850px"}}>

                <SkInput
                  title='Name'
                  placeholder='Enter certificate name'
                  error={this.state.nodeNameError}
                  disabled={this.state.validatingName}
                  onBlur={this.checkName}
                  valid={this.state.validNodeName}
                  updateVariable={this.setCertName}
                  value={this.state.skaleNodeName}
                />

                <div className='fl-cont padd-top-md marg-top-10'>
                  <div className='fl-col fl-grow'>
                    <h4 className="fs-6 g-4 fw-6">SSL Key</h4>
                  </div>
                </div>
                <input type="file" name="sslKey" className="padd-top-10 g-4"/>

                <div className='fl-cont padd-top-md marg-top-10'>
                  <div className='fl-col fl-grow'>
                    <h4 className="fs-6 g-4 fw-6">SSL Certificate</h4>
                  </div>
                </div>
                <input type="file" name="sslCert" className="padd-top-10 g-4"/>

                <br/>
                <br/>
                <Button className="marg-top-md marg-bott-10" size="md"
                        onClick={this.uploadCertificate}>
                  Upload files
                </Button>
              </form>
            </div>
          </div>
        </div>
      </Container>
    );
  }
}

export default withRouter(UploadCertificate);